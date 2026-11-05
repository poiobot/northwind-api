"""
SqlAlchemyDAO: the DAOInterface on relational databases, with SQLAlchemy Core, so the same code works on
SQLite, PostgreSQL, MySQL...: only the URL given to the constructor changes.

How the document-store contract maps onto SQL tables:
- An id is a primary key value. A composite key takes a tuple, e.g. find_by_id("Order Details", (10248, 11)).
  On writes, "id" or "_id" in a record (MongoDAO style) fills a primary key the record doesn't name.
- The bookkeeping columns _version, _created, _updated and _state are used only when the table has them:
  a SQL table has a fixed schema, so the DAO never adds columns.
- A logical delete sets _state = "DELETED", so it needs that column. Reads hide those rows unless
  include_deleted=True.
- A query is a list of (key, op, value) conditions, ANDed; a (key, value) pair means ==.
  Operators: ==, !=, <, <=, >, >=, in, not-in, like (substring).
- expand follows the foreign keys the database declares: a foreign-key column ("CustomerID") becomes the
  row it points at, and the name of a table that points here ("Order Details") adds the list of its rows.

Tables are described once, by asking the database (reflection), and kept for the life of the DAO:
create a new DAO after changing a table's columns.

Needs SQLAlchemy:   pip install sqlalchemy
Run from anywhere:  python src/sandbox/sql_alchemy_dao.py
"""
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import uuid4

from sqlalchemy import MetaData, String, Table, and_, create_engine, func, inspect, select, text, tuple_
from sqlalchemy.exc import IntegrityError, NoSuchTableError

from dao_interface import DAOInterface

logger = logging.getLogger(__name__)

Query = Optional[List[Tuple]]                               # [(key, op, value), ...]; (key, value) means ==
Keys = Union[List[str], str, None]                          # a list of columns, or "*" / None for all of them
Expand = Optional[List[Union[str, Tuple[str, str, bool]]]]  # column or table names, or (key, table, is_array)


class SqlAlchemyDAO(DAOInterface):

    # Bookkeeping columns, written only when the table has them
    VERSION, CREATED, UPDATED, STATE = "_version", "_created", "_updated", "_state"
    DELETED = "DELETED"

    # Query operators as SQLAlchemy expressions. != and not-in keep NULLs, as Mongo's $ne and $nin keep
    # missing fields (a plain SQL "<>" or "NOT IN" would drop them). like is a substring match: % and _ in
    # the value are escaped, so they match themselves.
    OPS = {
        "==": lambda column, value: column == value,  # == None is written IS NULL
        "!=": lambda column, value: column.is_distinct_from(value),
        "<": lambda column, value: column < value,
        "<=": lambda column, value: column <= value,
        ">": lambda column, value: column > value,
        ">=": lambda column, value: column >= value,
        "in": lambda column, value: column.in_(list(value)),
        "not-in": lambda column, value: column.is_(None) | column.not_in(list(value)),
        "like": lambda column, value: column.contains(str(value), autoescape=True),
    }

    def __init__(self, url: str, **engine_options):
        # A database URL, e.g. "sqlite:///database/sqlite/northwind.db" or
        # "postgresql://user:password@localhost/northwind". The engine opens connections when needed.
        # engine_options go to create_engine: echo=True prints every SQL statement the DAO sends.
        self.engine = create_engine(url, **engine_options)
        self._tables = MetaData()  # tables already described by the database, see _table
        self._description = None   # describe()'s result, built once

    # ---------------------------------------------------------------------------------------------- helpers

    def _table(self, name: str) -> Table:
        """
        Describes a table by asking the database (reflection): its columns, primary key and foreign keys,
        from whatever database the engine points at. Each table is read once; tables its foreign keys point
        at come along. An unknown table raises NoSuchTableError.
        Use the table's exact name ("Customers", not "customers"): on SQLite, SQLAlchemy finds the primary
        key only under the exact name.
        """
        if name not in self._tables.tables:
            Table(name, self._tables, autoload_with=self.engine)
        return self._tables.tables[name]

    @staticmethod
    def _pk(tbl: Table) -> list:
        key = list(tbl.primary_key.columns)
        if not key:
            raise ValueError(f"{tbl.name} has no primary key")
        return key

    def _pk_match(self, tbl: Table, id: Any):
        """WHERE clause for one primary key value; a composite key takes one value per key column."""
        key = self._pk(tbl)
        values = list(id) if isinstance(id, (tuple, list)) else [id]
        if len(values) != len(key):
            raise ValueError(f"{tbl.name} is keyed by {[column.name for column in key]}: pass one value per key column")
        return and_(*[column == value for column, value in zip(key, values)])

    def _pk_in(self, tbl: Table, ids: List):
        """WHERE clause for a list of primary key values (tuples for a composite key)."""
        key = self._pk(tbl)
        if len(key) == 1:
            return key[0].in_(list(ids))
        return tuple_(*key).in_([tuple(id) for id in ids])

    def _condition(self, tbl: Table, condition: Tuple):
        """One (key, op, value) or (key, value) tuple as a SQL condition."""
        if len(condition) == 2:
            (key, value), op = condition, "=="
        else:
            key, op, value = condition
        op = op.lower()
        if op == "all-in":
            raise ValueError("all-in matches array fields: a SQL column holds one value per row")
        if op not in self.OPS:
            raise ValueError(f"Unknown operator {op!r}: use one of {list(self.OPS)}")
        return self.OPS[op](tbl.c[key], value)  # tbl.c[key] raises KeyError for a column the table doesn't have

    def _live(self, tbl: Table, include_deleted: bool = False) -> list:
        """The condition that hides logically deleted rows, if the table has a _state column."""
        if include_deleted or self.STATE not in tbl.c:
            return []
        return [tbl.c[self.STATE].is_distinct_from(self.DELETED)]  # keeps rows whose _state is NULL

    def _random(self):
        return {"mysql": func.rand, "mariadb": func.rand, "mssql": func.newid}.get(self.engine.dialect.name, func.random)()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _values(self, tbl: Table, record: Dict) -> Dict:
        """
        A copy of record ready to write: the caller's dict is left as it was. MongoDAO callers name the key
        "id" or "_id"; unless the table has a column with that name, the value goes to the primary key.
        """
        values = dict(record)
        for alias in ("id", "_id"):
            if alias not in values or alias in tbl.c:
                continue
            given = values.pop(alias)
            if given is None:
                continue
            key = self._pk(tbl)
            parts = list(given) if isinstance(given, (tuple, list)) else [given]
            if len(parts) != len(key):
                raise ValueError(f"{tbl.name} is keyed by {[column.name for column in key]}: {alias}={given!r} doesn't fit")
            for column, part in zip(key, parts):
                values.setdefault(column.name, part)
        return values

    def _new_key(self, tbl: Table, values: Dict):
        """A missing single text key gets a new id, as MongoDAO does for _id. Integer keys are left to the
        database, which numbers them itself (autoincrement)."""
        key = self._pk(tbl)
        if len(key) == 1 and values.get(key[0].name) is None and isinstance(key[0].type, String):
            values[key[0].name] = self.id(tbl.name)

    def _stamp_new(self, tbl: Table, values: Dict, timestamp: bool = True, version: bool = True):
        if version and self.VERSION in tbl.c:
            values[self.VERSION] = 1
        if timestamp:
            now = self._now()
            for name in (self.CREATED, self.UPDATED):
                if name in tbl.c:
                    values[name] = now

    def _stamp_change(self, tbl: Table, changes: Dict, timestamp: bool = True, version: bool = True):
        if timestamp and self.UPDATED in tbl.c:
            changes[self.UPDATED] = self._now()
        if version and self.VERSION in tbl.c:
            # Computed by the database, so two writers can't both write the same version;
            # COALESCE counts a NULL version (a row written outside the DAO) as 0
            changes[self.VERSION] = func.coalesce(tbl.c[self.VERSION], 0) + 1

    @staticmethod
    def _row(con, tbl: Table, match) -> Optional[Dict]:
        """Reads a row back inside the write's transaction, so the caller gets what was stored."""
        row = con.execute(select(tbl).where(match)).mappings().first()
        return dict(row) if row else None

    def _joins(self, tbl: Table, expand: Expand, meta: Dict = None) -> List[Tuple]:
        """
        Turns expand into (key, local column, target table, target column, is_list) joins, from the foreign
        keys the database declares:
        - "CustomerID", a foreign-key column: the row it points at replaces its value.
        - "Order Details", a table with a foreign key to this one: the list of its rows is added under that name.
        - ("CustomerID", "Customers", False), or MongoDAO's meta: for a column with no declared foreign key;
          it points at the target table's primary key.
        """
        if not expand:
            return []
        if meta:
            references = meta.get("references", {})
            for key in expand:
                if key not in references:
                    logger.warning(f"{key} not in {meta.get('class', 'Unknown')} references")
            expand = [(key, references[key]["table"], references[key]["is_array"]) for key in expand if key in references]

        joins = []
        for item in expand:
            if isinstance(item, (tuple, list)):
                key, target, is_array = item
                if is_array:
                    raise NotImplementedError(f"{key}: a SQL column holds one id, not a list. To add the rows of a "
                                              f"table that points at {tbl.name}, expand that table's name")
                target_key = self._pk(self._table(target))
                if len(target_key) != 1:
                    raise NotImplementedError(f"{target} has a composite key: only single-column references can be expanded")
                joins.append((key, tbl.c[key], target_key[0].table, target_key[0], False))
            elif item in tbl.c:
                foreign_keys = list(tbl.c[item].foreign_keys)
                if not foreign_keys:
                    raise ValueError(f"{tbl.name}.{item} has no foreign key: expand ({item!r}, <table>, False) instead")
                link = foreign_keys[0]
                if len(link.constraint.elements) > 1:
                    raise NotImplementedError(f"{tbl.name}.{item} is part of a composite foreign key")
                joins.append((item, link.parent, link.column.table, link.column, False))
            else:
                try:
                    child = self._table(item)
                except NoSuchTableError:
                    raise ValueError(f"{item!r} is neither a column of {tbl.name} nor a table") from None
                links = [fk for fk in child.foreign_keys if fk.column.table is tbl]
                if len(links) != 1:
                    raise ValueError(f"{item} has {len(links)} foreign keys to {tbl.name}: expand needs exactly one")
                if len(links[0].constraint.elements) > 1:
                    raise NotImplementedError(f"{item} points at {tbl.name} with a composite foreign key")
                joins.append((item, links[0].column, child, links[0].parent, True))
        return joins

    def _expand(self, rows: List[Dict], joins: List[Tuple], include_deleted: bool):
        """One extra query per join, however many rows: the related rows are read with IN and matched in
        Python, so each row gets nested dicts, as MongoDAO's $lookup gives."""
        for key, local, target, remote, is_list in joins:
            values = list({row[local.name] for row in rows} - {None})
            related = []
            if values:
                query = select(target).where(remote.in_(values), *self._live(target, include_deleted))
                with self.engine.connect() as con:
                    related = [dict(row) for row in con.execute(query).mappings()]
            if is_list:
                children = defaultdict(list)
                for row in related:
                    children[row[remote.name]].append(row)
                for row in rows:
                    row[key] = children.get(row[local.name], [])
            else:
                by_key = {row[remote.name]: row for row in related}
                for row in rows:
                    match = by_key.get(row[local.name])
                    row[key] = dict(match) if match else None  # a copy per row: rows can share a reference

    def _select(self, tbl: Table, where: list, keys: Keys = "*", expand: Expand = None, meta: Dict = None,
                sort_by: List[Tuple[str, int]] = None, sample: int = 0, include_deleted: bool = False) -> List[Dict]:
        """The one SELECT behind every read: conditions, columns, sort, sample and joins."""
        joins = self._joins(tbl, expand, meta)
        sort = [(key, direction) for key, direction in sort_by or [] if direction in (1, -1)]

        # 1. Choose the columns to return. No manual check needed: tbl.c[name] only knows the table's real
        #    columns and raises KeyError for any other name. Some columns are read only for internal use (the
        #    local side of each join, and the sort keys when sampling) and are dropped before returning.
        wanted = [column.name for column in tbl.c] if keys in ("*", None) else [tbl.c[key].name for key in keys]
        internal = [local.name for _, local, *_ in joins] + ([key for key, _ in sort] if sample > 0 else [])
        names = list(dict.fromkeys(wanted + internal))
        hidden = set(names) - set(wanted) - {key for key, *_ in joins}

        # 2. Build the query from Python objects. SQLAlchemy writes the SQL for this database, quotes the
        #    names and sends the values as parameters.
        query = select(*[tbl.c[name] for name in names]).where(*where, *self._live(tbl, include_deleted))
        columns = tbl.c
        if sample > 0:
            # Draw the sample first and sort it afterwards, so the sort isn't lost
            sampled = query.order_by(self._random()).limit(sample).subquery()
            query, columns = select(sampled), sampled.c
        query = query.order_by(*[columns[key].asc() if direction == 1 else columns[key].desc() for key, direction in sort])

        with self.engine.connect() as con:  # the connection goes back to the engine's pool afterwards
            rows = [dict(row) for row in con.execute(query).mappings()]

        # 3. Joins, then drop the internal columns
        self._expand(rows, joins, include_deleted)
        for row in rows:
            for name in hidden:
                row.pop(name, None)
        return rows

    def _delete(self, tbl: Table, where: list, physical_delete: bool) -> int:
        if physical_delete:
            with self.engine.begin() as con:  # commits at the end of the block, rolls back on an error
                return con.execute(tbl.delete().where(*where)).rowcount
        if self.STATE not in tbl.c:
            raise ValueError(f"{tbl.name} has no {self.STATE} column for a logical delete: add one, or pass physical_delete=True")
        changes = {self.STATE: self.DELETED}
        self._stamp_change(tbl, changes)
        with self.engine.begin() as con:
            # Rows already deleted are left alone, so they aren't counted again
            return con.execute(tbl.update().where(*where, *self._live(tbl)).values(changes)).rowcount

    # ------------------------------------------------------------------------------------- DAOInterface

    def describe(self) -> Dict:
        """
        Every table and its columns, with the Python type of each column ("str", "int", "datetime"...), or
        the SQL type when there is no Python one. Built once.
        """
        if self._description is None:
            inspector = inspect(self.engine)
            self._description = {
                table: {column["name"]: self._type_name(column["type"]) for column in inspector.get_columns(table)}
                for table in inspector.get_table_names()
            }
        return self._description

    @staticmethod
    def _type_name(sql_type) -> str:
        try:
            return sql_type.python_type.__name__
        except NotImplementedError:
            return str(sql_type)

    def id(self, table: str = None) -> str:
        """A new unique id (32 hex characters), for text keys. Integer keys are numbered by the database."""
        return uuid4().hex

    def insert(self, table: str, record: Dict, get_next_id: bool = False, timestamp: bool = True,
               version: bool = True) -> Optional[Dict]:
        """
        Inserts one row and returns it as stored (defaults and generated keys included), or None when the
        database rejects it: duplicate key, NOT NULL, foreign key...
        get_next_id is accepted for the interface and unused, as in MongoDAO: a missing single text key always
        gets a new id, and a missing integer key is numbered by the database.
        """
        tbl = self._table(table)
        values = self._values(tbl, record)
        self._new_key(tbl, values)
        self._stamp_new(tbl, values, timestamp, version)
        try:
            with self.engine.begin() as con:
                result = con.execute(tbl.insert().values(values))
                id = tuple(result.inserted_primary_key)
                return self._row(con, tbl, self._pk_match(tbl, id))
        except IntegrityError as error:
            logger.warning(f"Insert rejected (table={table}): {error.orig}")
            return None

    def upsert(self, table: str, record: Dict, get_next_id: bool = False, timestamp: bool = True,
               version: bool = True) -> Optional[Dict]:
        """
        Inserts the row, or updates it when its primary key already exists, and returns it as stored (None if
        the database rejects it). An update keeps _created and adds 1 to _version.
        Unlike MongoDAO's replace, columns missing from record keep their values: a SQL row always has every
        column, and blanking the missing ones would break NOT NULL columns.
        """
        tbl = self._table(table)
        values = self._values(tbl, record)
        key_names = [column.name for column in self._pk(tbl)]
        if any(values.get(name) is None for name in key_names):
            return self.insert(table, values, get_next_id, timestamp, version)  # no key: nothing to replace
        id = tuple(values[name] for name in key_names)
        match = self._pk_match(tbl, id)
        try:
            with self.engine.begin() as con:
                # FOR UPDATE locks the row until the block ends, where the database supports it (PostgreSQL,
                # MySQL); SQLite locks the whole database while writing instead
                exists = con.execute(select(*self._pk(tbl)).where(match).with_for_update()).first() is not None
                if exists:
                    changes = {name: value for name, value in values.items()
                               if name not in key_names and name not in (self.VERSION, self.CREATED)}
                    self._stamp_change(tbl, changes, timestamp, version)
                    if changes:
                        con.execute(tbl.update().where(match).values(changes))
                else:
                    self._stamp_new(tbl, values, timestamp, version)
                    con.execute(tbl.insert().values(values))
                return self._row(con, tbl, match)
        except IntegrityError as error:
            logger.warning(f"Upsert rejected (table={table}, id={id}): {error.orig}")
            return None

    def update(self, table: str, id: Any, record: Dict, timestamp: bool = True) -> Optional[Dict]:
        """
        Changes the given columns of one row and returns the row as stored, or None if there is no such row
        or the database rejects the change. The primary key, _version and _created are skipped, as MongoDAO
        skips _id and _version; _version goes up by 1 when the table has it.
        Works on logically deleted rows too: update(table, id, {"_state": None}) restores one.
        """
        tbl = self._table(table)
        protected = {column.name for column in self._pk(tbl)} | {self.VERSION, self.CREATED}
        changes = {name: value for name, value in self._values(tbl, record).items() if name not in protected}
        self._stamp_change(tbl, changes, timestamp)
        match = self._pk_match(tbl, id)
        try:
            with self.engine.begin() as con:
                if changes:
                    con.execute(tbl.update().where(match).values(changes))
                return self._row(con, tbl, match)
        except IntegrityError as error:
            logger.warning(f"Update rejected (table={table}, id={id}): {error.orig}")
            return None

    def find_by_id(self, table: str, id: Any, keys: Keys = "*", expand: Expand = None, meta: Dict = None,
                   *, include_deleted: bool = False) -> Optional[Dict]:
        """
        Locates a record by its primary key and returns it as a dict, or None if there is no such row.
        A composite key takes a tuple, e.g. find_by_id("Order Details", (10248, 11)) for OrderID 10248, ProductID 11.
        """
        tbl = self._table(table)
        rows = self._select(tbl, [self._pk_match(tbl, id)], keys, expand, meta, include_deleted=include_deleted)
        return rows[0] if rows else None

    def find_objects_list(self, table: str, ids: List, expand: Expand = None, keys: Keys = "*", meta: Dict = None,
                          *, include_deleted: bool = False) -> List[Dict]:
        """The rows whose primary key is in ids (tuples for a composite key). Missing ids are skipped."""
        tbl = self._table(table)
        return self._select(tbl, [self._pk_in(tbl, ids)], keys, expand, meta, include_deleted=include_deleted)

    def find_by_key_value(self, table: str, key: str, op: str = "==", value: Any = None, expand: Expand = None,
                          keys: Keys = "*", meta: Dict = None, *, include_deleted: bool = False) -> List[Dict]:
        """The rows where key op value holds, e.g. ("UnitPrice", ">", 20). Operators: see OPS."""
        return self.fetch(table, [(key, op, value)], expand, keys, meta=meta, include_deleted=include_deleted)

    def find_by_key_value_like(self, table: str, key: str, value: Any, expand: Expand = None, keys: Keys = "*",
                               meta: Dict = None, *, include_deleted: bool = False) -> List[Dict]:
        """The rows whose key contains value. Case sensitivity is the database's: SQLite and MySQL ignore case
        by default, PostgreSQL doesn't."""
        return self.fetch(table, [(key, "like", value)], expand, keys, meta=meta, include_deleted=include_deleted)

    def fetch(self, table: str, query: Query = None, expand: Expand = None, keys: Keys = "*",
              sort_by: List[Tuple[str, int]] = None, meta: Dict = None,
              *, sample: int = 0, include_deleted: bool = False) -> List[Dict]:
        """
        The rows matching every condition in query (all rows without one).
        :param query: [(key, op, value), ...], ANDed; a (key, value) pair means ==
        :param expand: foreign-key columns to replace by their rows, or tables pointing here to add (see _joins)
        :param keys: columns to return, all of them by default; expanded keys are always returned
        :param sort_by: [(key, 1 for ascending or -1 for descending), ...]
        :param sample: return this many random rows (sorted by sort_by afterwards)
        :param include_deleted: also return logically deleted rows
        """
        tbl = self._table(table)
        where = [self._condition(tbl, condition) for condition in query or []]
        return self._select(tbl, where, keys, expand, meta, sort_by, sample, include_deleted)

    def delete(self, table: str, id: Any, physical_delete: bool = False) -> bool:
        """
        Deletes one row by primary key: logically by default (_state = "DELETED", which needs that column),
        or for good with physical_delete=True. True if a row was deleted.
        """
        tbl = self._table(table)
        return self._delete(tbl, [self._pk_match(tbl, id)], physical_delete) > 0

    def delete_objects_list(self, table: str, ids: List, physical_delete: bool = False) -> int:
        """Deletes the rows whose primary key is in ids and returns how many were deleted."""
        tbl = self._table(table)
        return self._delete(tbl, [self._pk_in(tbl, ids)], physical_delete)

    def delete_many(self, table: str, query: Query, physical_delete: bool = False) -> int:
        """
        Deletes the rows matching query and returns how many were deleted. An empty query raises ValueError
        rather than deleting every row: delete_all says that on purpose.
        """
        if not query:
            raise ValueError("delete_many needs at least one condition: use delete_all to delete every row")
        tbl = self._table(table)
        return self._delete(tbl, [self._condition(tbl, condition) for condition in query], physical_delete)

    def delete_all(self, table: str, physical_delete: bool = False) -> int:
        """Deletes every row of the table and returns how many were deleted. The table itself stays."""
        return self._delete(self._table(table), [], physical_delete)

    def distinct(self, table: str, key: str, query: Query = None, *, include_deleted: bool = False) -> List[Any]:
        """
        The unique values of one column among the rows matching query. query takes (key, value) pairs, as the
        interface documents, or (key, op, value) tuples, as fetch does.
        """
        tbl = self._table(table)
        where = [self._condition(tbl, condition) for condition in query or []]
        statement = select(tbl.c[key]).distinct().where(*where, *self._live(tbl, include_deleted))
        with self.engine.connect() as con:
            return list(con.execute(statement).scalars())

    def execute_raw_query(self, table: str, query: Union[Tuple[str, Union[Dict, List]], str]) -> Any:
        """
        Runs SQL written by hand, for what the other methods can't express: query is (sql, parameters), with
        :name placeholders in the SQL and their values in a dict (a list of dicts runs it once per dict).
        Never paste values into the SQL text: parameters are what keep it safe from SQL injection.
        Returns the rows as dicts for a statement that returns rows, otherwise the number of rows affected.
        table is unused: the SQL names its own tables. Not portable: the SQL is this database's dialect.
        """
        sql, parameters = (query, None) if isinstance(query, str) else query
        with self.engine.begin() as con:
            result = con.execute(text(sql), parameters or {})
            if result.returns_rows:
                return [dict(row) for row in result.mappings()]
            return result.rowcount

    def drop(self, table: str):
        """Deletes the table itself, as MongoDAO.drop does with a collection."""
        tbl = self._table(table)
        tbl.drop(self.engine)
        self._tables.remove(tbl)
        self._description = None


if __name__ == "__main__":
    import json
    northwind = Path(__file__).resolve().parents[2] / "database" / "sqlite" / "northwind.db"
    dao = SqlAlchemyDAO(f"sqlite:///{northwind}")
    print(json.dumps(dao.describe(),indent=4))  # another database only needs another URL; echo=True shows the SQL
    print(dao.find_by_id("Customers", "ALFKI", keys=["CustomerID", "CompanyName", "City"]))  # text key
    print(dao.find_by_id("Orders", 10248, keys=["OrderID", "CustomerID", "OrderDate"]))     # integer key
    print(dao.find_by_id("Order Details", (10248, 11)))                                      # composite key
    print(dao.find_by_id("Customers", "NOPE!"))                                              # no such row

    # Queries: (key, op, value) conditions, ANDed
    print(dao.fetch("Products", [("UnitPrice", ">", 50)], keys=["ProductName", "UnitPrice"], sort_by=[("UnitPrice", -1)]))
    print(dao.find_by_key_value_like("Customers", "CompanyName", "market", keys=["CompanyName"]))
    print(dao.distinct("Customers", "Country", [("City", "in", ["London", "Madrid"])]))

    # Joins follow the foreign keys: a key column becomes its row, a table pointing here adds its rows
    order = dao.find_by_id("Orders", 10248, keys=["OrderID", "OrderDate"], expand=["CustomerID", "Order Details"])
    print(order["CustomerID"]["CompanyName"], [line["ProductID"] for line in order["Order Details"]])

    # Writes, on a throwaway in-memory database whose table has the bookkeeping columns
    scratch = SqlAlchemyDAO("sqlite://")
    scratch.execute_raw_query("staff", """
        CREATE TABLE staff (staff_id TEXT PRIMARY KEY, name TEXT NOT NULL, team TEXT,
                            _version INTEGER, _created DATETIME, _updated DATETIME, _state TEXT)""")
    member = scratch.insert("staff", {"name": "Vanesa", "team": "Data"})   # staff_id generated, _version 1
    print(scratch.update("staff", member["staff_id"], {"team": "Platform"}))  # _version 2
    print(scratch.delete("staff", member["staff_id"]))                        # logical: _state = DELETED
    print(scratch.find_by_id("staff", member["staff_id"]))                    # None: hidden from reads
    print(scratch.find_by_id("staff", member["staff_id"], include_deleted=True))