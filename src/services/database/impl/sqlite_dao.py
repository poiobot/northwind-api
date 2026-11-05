"""
SqliteDAO: DAOInterface implemented with Python's built-in sqlite3 module (no extra packages).

Run the demo from the project root:  PYTHONPATH=src python src/services/database/impl/sqlite_dao.py

What SQLite asks of a DAO, and where to look below:
- Connections: one short-lived connection per operation (_connection). Each write is a transaction
  that commits on success and rolls back on error.
- Parameters: values always travel as ? parameters, never pasted into the SQL. Table and column
  names can't be parameters, so they are checked against the schema and quoted (_column, _quote).
  The check matters: SQLite reads an unknown "quoted name" as a string literal instead of failing.
- Keys: read from the schema, not assumed. Northwind has text keys (CustomerID), integer keys that
  SQLite numbers itself (CategoryID) and composite keys ("Order Details": OrderID + ProductID).
  "_id" and "id" are accepted for a single-column key, so Spore-style records work.
- Bookkeeping: Spore's _version, _created, _updated and _state columns are maintained only on
  tables that have them. The Northwind tables don't.
- Foreign keys are enforced. SQLite ignores them unless each connection switches them on.
"""
import logging
import shutil
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple
from uuid import uuid4

from services.database.dao_interface import DAOInterface

logger = logging.getLogger(__name__)

# Query DSL operator -> SQL operator
OPERATORS = {
    "==": "=", "!=": "!=", ">": ">", ">=": ">=", "<": "<", "<=": "<=",
    "like": "LIKE", "in": "IN", "not-in": "NOT IN",
}

# Spore's bookkeeping fields. Records written to a table without these columns just lose them.
BOOKKEEPING = ("_version", "_created", "_updated", "_state")


def _quote(name: str) -> str:
    """Quote a table or column name. "Order Details" needs it; doubling inner quotes keeps it safe."""
    return '"' + name.replace('"', '""') + '"'


def _placeholders(count: int) -> str:
    return ", ".join(["?"] * count)


def _as_list(value: Any) -> list:
    """Accept "a, b" as well as ["a", "b"]."""
    if isinstance(value, str):
        return [part.strip() for part in value.split(",")]
    return list(value or [])


def _now() -> str:
    # Stored as ISO-8601 text: sqlite3's built-in datetime adapter is deprecated since Python 3.12.
    return datetime.now(timezone.utc).isoformat()


class SqliteDAO(DAOInterface):

    def __init__(self, dbname: str):
        """
        :param dbname: path to the SQLite database file
        """
        self.dbname = dbname
        self._schema: Dict[str, List[sqlite3.Row]] = {}  # lower-case table name -> PRAGMA table_info rows

    # ---------------------------------------------------------------- DAOInterface

    def describe(self) -> Dict:
        """{table: {column: declared type}} for every table; views and SQLite's own tables are left out."""
        with self._connection() as con:
            tables = [row["name"] for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite\\_%' ESCAPE '\\' ORDER BY name")]
        return {table: {column["name"]: column["type"] for column in self._table_info(table)} for table in tables}

    def id(self, table: Optional[str] = None) -> Any:
        """
        Next key for a table: integer keys continue after the highest one, anything else gets a UUID.
        "INT" anywhere in the declared type is SQLite's own rule for integer columns.
        """
        if table and "INT" in self._key_type(table):
            key = _quote(self._primary_key(table)[0])
            with self._connection() as con:
                return con.execute(f"SELECT COALESCE(MAX({key}), 0) + 1 FROM {_quote(table)}").fetchone()[0]
        return str(uuid4())

    def insert(self, table: str, record: Dict, get_next_id: bool = False,
               timestamp: bool = True, version: bool = True) -> Optional[Dict]:
        """
        Insert one row and return it as stored (column defaults included), or None when a constraint
        rejects it: duplicate key, NOT NULL, CHECK or FOREIGN KEY.
        """
        row = self._new_row(table, record, get_next_id, timestamp, version)
        columns = ", ".join(_quote(column) for column in row)
        cursor = self._write(table, f"INSERT INTO {_quote(table)} ({columns}) VALUES ({_placeholders(len(row))})",
                             list(row.values()))
        return self._read_back(table, row, cursor.lastrowid) if cursor else None

    def upsert(self, table: str, record: Dict, get_next_id: bool = False,
               timestamp: bool = True, version: bool = True) -> Optional[Dict]:
        """
        Insert the row, or update it when its key already exists (INSERT ... ON CONFLICT DO UPDATE).
        An update overwrites the columns given, keeps the others and _created, and adds 1 to _version.
        """
        key = self._primary_key(table)
        if not key:
            raise ValueError(f"{table} has no primary key to recognise existing rows by")
        row = self._new_row(table, record, get_next_id, timestamp, version)
        columns = ", ".join(_quote(column) for column in row)
        # Inside DO UPDATE, excluded.X is the value we tried to insert and a bare X the value stored.
        changes = [f"{_quote(column)} = excluded.{_quote(column)}" for column in row
                   if column not in key and column not in ("_created", "_version")]
        if "_version" in row:
            changes.append('"_version" = COALESCE("_version", 0) + 1')
        action = f"DO UPDATE SET {', '.join(changes)}" if changes else "DO NOTHING"
        sql = (f"INSERT INTO {_quote(table)} ({columns}) VALUES ({_placeholders(len(row))}) "
               f"ON CONFLICT ({', '.join(_quote(column) for column in key)}) {action}")
        cursor = self._write(table, sql, list(row.values()))
        return self._read_back(table, row, cursor.lastrowid) if cursor else None

    def update(self, table: str, id: Any, record: Dict, timestamp: bool = True) -> Optional[Dict]:
        """
        Update the given columns of one row and return it as stored, or None when no row has that key
        or a constraint rejects the change. The key, _version and the timestamps are managed here.
        """
        where, where_params = self._match_id(table, id)
        managed = set(self._primary_key(table)) | {"_version", "_created", "_updated"}
        changes = {column: value for column, value in self._row(table, record).items() if column not in managed}
        assignments = [f"{_quote(column)} = ?" for column in changes]
        params = list(changes.values())
        columns = self._columns(table)
        if timestamp and "_updated" in columns:
            assignments.append('"_updated" = ?')
            params.append(_now())
        if "_version" in columns:
            assignments.append('"_version" = COALESCE("_version", 0) + 1')
        if not assignments:
            return self.find_by_id(table, id)
        cursor = self._write(table, f"UPDATE {_quote(table)} SET {', '.join(assignments)} WHERE {where}",
                             params + where_params)
        return self.find_by_id(table, id) if cursor and cursor.rowcount else None

    def find_by_id(self, table: str, id: Any, keys: Any = "*", expand: Optional[List] = None,
                   meta: Optional[Dict] = None) -> Optional[Dict]:
        """
        One row by key, or None. A composite key takes one value per key column, as a tuple in key
        order or as a dict. Example: dao.find_by_id("Order Details", (10248, 11)) reads the line
        with OrderID 10248 and ProductID 11.
        """
        where, params = self._match_id(table, id)
        rows = self._select(table, where, params, keys=keys, expand=expand, meta=meta)
        return rows[0] if rows else None

    def find_objects_list(self, table: str, ids: List, expand: Optional[List] = None, keys: Any = "*",
                          meta: Optional[Dict] = None) -> List[Dict]:
        if not ids:
            return []
        where, params = self._match_ids(table, ids)
        return self._select(table, where, params, keys=keys, expand=expand, meta=meta)

    def find_by_key_value(self, table: str, key: str, op: str = "==", value: Any = None,
                          expand: Optional[List] = None, keys: Any = "*", meta: Optional[Dict] = None) -> List[Dict]:
        return self.fetch(table, query=[(key, op, value)], expand=expand, keys=keys, meta=meta)

    def find_by_key_value_like(self, table: str, key: str, value: Any, expand: Optional[List] = None,
                               keys: Any = "*", meta: Optional[Dict] = None) -> List[Dict]:
        return self.fetch(table, query=[(key, "like", value)], expand=expand, keys=keys, meta=meta)

    def fetch(self, table: str, query: Optional[List[Tuple]] = None, expand: Optional[List] = None,
              keys: Any = "*", sort_by: Optional[List[Tuple[str, int]]] = None,
              meta: Optional[Dict] = None) -> List[Dict]:
        """
        Rows matching every condition in query: (field, operator, value) with ==, !=, >, >=, <, <=,
        like (substring, case-insensitive), in, not-in. A (field, value) pair means ==.
        expand replaces foreign key values with the rows they point to.
        """
        where, params = self._where(table, query)
        return self._select(table, where, params, keys=keys, sort_by=sort_by, expand=expand, meta=meta)

    def delete(self, table: str, id: Any, physical_delete: bool = False) -> bool:
        """
        Delete one row, or mark it _state = 'DELETED' when physical_delete is False. True if it existed.
        Raises sqlite3.IntegrityError while other rows still reference it.
        """
        where, params = self._match_id(table, id)
        return self._remove(table, where, params, physical_delete) > 0

    def delete_objects_list(self, table: str, ids: List, physical_delete: bool = False) -> int:
        if not ids:
            return 0
        where, params = self._match_ids(table, ids)
        return self._remove(table, where, params, physical_delete)

    def delete_many(self, table: str, query: Optional[List[Tuple]], physical_delete: bool = False) -> int:
        """Delete the rows matching query. An empty query is refused: use delete_all to mean everything."""
        if not query:
            raise ValueError("delete_many needs at least one condition; use delete_all to delete every row")
        where, params = self._where(table, query)
        return self._remove(table, where, params, physical_delete)

    def delete_all(self, table: str, physical_delete: bool = False) -> int:
        return self._remove(table, "", [], physical_delete)

    def distinct(self, table: str, key: str, query: Optional[List[Tuple]] = None) -> List[Any]:
        column = _quote(self._column(table, key))
        where, params = self._where(table, query)
        sql = f"SELECT DISTINCT {column} FROM {_quote(table)}" + (f" WHERE {where}" if where else "")
        with self._connection() as con:
            return [row[0] for row in con.execute(sql, params)]

    def execute_raw_query(self, table: str, query: Tuple[str, Any]) -> Any:
        """
        Run one SQL statement given as (sql, params): ? placeholders take a list, :name ones a dict.
        Returns the rows as dicts when the statement produces rows, otherwise the number of rows changed.
        The table argument is unused (the SQL names its tables); the interface requires it.
        """
        if isinstance(query, str):
            query = (query,)
        sql, params = query[0], query[1] if len(query) > 1 else ()
        self._schema.clear()  # the statement may ALTER or DROP tables
        with self._connection() as con:
            cursor = con.execute(sql, params)
            if cursor.description is None:  # INSERT, UPDATE, DELETE, CREATE...: no result columns
                return cursor.rowcount
            return [dict(row) for row in cursor]

    # ---------------------------------------------------------------- connection and schema

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.dbname)
        con.row_factory = sqlite3.Row            # rows readable by column name, convertible with dict()
        con.execute("PRAGMA foreign_keys = ON")  # off by default, and it is a per-connection setting
        try:
            with con:                            # commits if the block succeeds, rolls back if it raises
                yield con
        finally:
            con.close()                          # "with con" ends the transaction but doesn't close

    def _table_info(self, table: str) -> List[sqlite3.Row]:
        """The table's (or view's) columns: name, type, notnull, dflt_value, pk. Cached."""
        if table.lower() not in self._schema:
            with self._connection() as con:
                columns = con.execute(f"PRAGMA table_info({_quote(table)})").fetchall()
            if not columns:
                raise ValueError(f"No table named {table!r} in {self.dbname}")
            self._schema[table.lower()] = columns
        return self._schema[table.lower()]

    def _columns(self, table: str) -> List[str]:
        return [column["name"] for column in self._table_info(table)]

    def _primary_key(self, table: str) -> List[str]:
        """Key column(s) in key order: ["CustomerID"], ["OrderID", "ProductID"], or [] when there is none."""
        key = sorted((column for column in self._table_info(table) if column["pk"]), key=lambda column: column["pk"])
        return [column["name"] for column in key]

    def _key_type(self, table: str) -> str:
        """Declared type of a single-column key, upper-cased ("TEXT", "INTEGER", ...); "" otherwise."""
        key = self._primary_key(table)
        types = {column["name"]: column["type"].upper() for column in self._table_info(table)}
        return types[key[0]] if len(key) == 1 else ""

    # ---------------------------------------------------------------- names, keys and queries

    def _column(self, table: str, name: str) -> str:
        """A column's real name, given in any letter case. "_id" and "id" name a single-column key."""
        for column in self._columns(table):
            if column.lower() == name.lower():
                return column
        key = self._primary_key(table)
        if name in ("_id", "id") and len(key) == 1:
            return key[0]
        raise ValueError(f"{table} has no column {name!r}")

    def _row(self, table: str, record: Dict) -> Dict:
        """The record keyed by real column names, minus bookkeeping fields the table doesn't have."""
        columns = self._columns(table)
        return {self._column(table, field): value for field, value in record.items()
                if field not in BOOKKEEPING or field in columns}

    def _match_id(self, table: str, id: Any) -> Tuple[str, list]:
        """WHERE clause for one key: a plain value, or a tuple or dict for a composite key."""
        key = self._primary_key(table)
        if not key:
            raise ValueError(f"{table} has no primary key")
        if len(key) == 1:
            return f"{_quote(key[0])} = ?", [id]
        if isinstance(id, dict):
            given = self._row(table, id)
            values = [given.get(column) for column in key]
        else:
            values = list(id) if isinstance(id, (list, tuple)) else [id]
        if len(values) != len(key) or None in values:
            raise ValueError(f"{table} is keyed by {key}: give one value per column, e.g. a tuple")
        return " AND ".join(f"{_quote(column)} = ?" for column in key), values

    def _match_ids(self, table: str, ids: List) -> Tuple[str, list]:
        """WHERE clause for several keys."""
        key = self._primary_key(table)
        if len(key) == 1:
            return f"{_quote(key[0])} IN ({_placeholders(len(ids))})", list(ids)
        matches = [self._match_id(table, one) for one in ids]  # composite: (a = ? AND b = ?) OR (...)
        return " OR ".join(f"({sql})" for sql, _ in matches), [value for _, values in matches for value in values]

    def _where(self, table: str, query: Optional[List[Tuple]]) -> Tuple[str, list]:
        """The query DSL as a WHERE clause plus its parameters."""
        clauses, params = [], []
        for condition in query or []:
            field, op, value = condition if len(condition) == 3 else (condition[0], "==", condition[1])
            column, op = _quote(self._column(table, field)), op.lower()
            if op not in OPERATORS:
                raise ValueError(f"Unsupported operator {op!r}; use one of: {', '.join(OPERATORS)}")
            if op in ("in", "not-in"):
                values = [value] if isinstance(value, (str, bytes)) else list(value)
                clauses.append(f"{column} {OPERATORS[op]} ({_placeholders(len(values))})")
                params.extend(values)
            elif op == "like":
                # Substring match. % and _ in the value are escaped so they match themselves.
                text = str(value).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                clauses.append(f"{column} LIKE ? ESCAPE '\\'")
                params.append(f"%{text}%")
            elif value is None and op in ("==", "!="):
                # In SQL, NULL = NULL is not true: missing values are tested with IS NULL.
                clauses.append(f"{column} IS {'NOT ' if op == '!=' else ''}NULL")
            else:
                clauses.append(f"{column} {OPERATORS[op]} ?")
                params.append(value)
        return " AND ".join(clauses), params

    # ---------------------------------------------------------------- shared SQL

    def _select(self, table: str, where: str = "", params: Optional[list] = None, keys: Any = "*",
                sort_by: Optional[List[Tuple[str, int]]] = None, expand: Optional[List] = None,
                meta: Optional[Dict] = None) -> List[Dict]:
        """The SELECT behind every read: projection (keys), filter, sorting and expansion."""
        names = _as_list(keys)
        if names in ([], ["*"]):
            self._table_info(table)  # still fail clearly on an unknown table
            columns = "*"
        else:
            columns = ", ".join(_quote(self._column(table, name)) for name in names)
        sql = f"SELECT {columns} FROM {_quote(table)}"
        if where:
            sql += f" WHERE {where}"
        if sort_by:
            order = []
            for field, direction in sort_by:
                if direction not in (1, -1):
                    raise ValueError(f"Sort direction for {field!r} must be 1 (ascending) or -1 (descending)")
                order.append(f"{_quote(self._column(table, field))} {'ASC' if direction == 1 else 'DESC'}")
            sql += " ORDER BY " + ", ".join(order)
        with self._connection() as con:
            rows = [dict(row) for row in con.execute(sql, params or [])]
            for reference in _as_list(expand):
                self._expand(con, table, rows, reference, meta)
        return rows

    def _expand(self, con: sqlite3.Connection, table: str, rows: List[Dict], reference: Any,
                meta: Optional[Dict]) -> None:
        """Replace each row's foreign key value with the row it points to, using one query for all rows."""
        column, target, target_column = self._reference(con, table, reference, meta)
        values = list({row[column] for row in rows if row.get(column) is not None})
        if not values:
            return
        sql = f"SELECT * FROM {_quote(target)} WHERE {_quote(target_column)} IN ({_placeholders(len(values))})"
        found = {referenced[target_column]: dict(referenced) for referenced in con.execute(sql, values)}
        for row in rows:
            if row.get(column) in found:
                row[column] = found[row[column]]

    def _reference(self, con: sqlite3.Connection, table: str, reference: Any,
                   meta: Optional[Dict]) -> Tuple[str, str, str]:
        """(column, referenced table, referenced column) for one entry of expand."""
        references = (meta or {}).get("references") or {}
        target_column = None
        if isinstance(reference, (tuple, list)):  # explicit (field, table[, is_array]), as MongoDAO takes
            column, target = self._column(table, reference[0]), reference[1]
        elif reference in references:             # Spore metadata extracted from the domain model
            column, target = self._column(table, reference), references[reference]["table"]
        else:                                     # the FOREIGN KEY declared in the schema
            column = self._column(table, reference)
            foreign_keys = [fk for fk in con.execute(f"PRAGMA foreign_key_list({_quote(table)})")
                            if fk["from"].lower() == column.lower()]
            if not foreign_keys:
                raise ValueError(f"{table}.{column} is not a foreign key, so it can't be expanded")
            target, target_column = foreign_keys[0]["table"], foreign_keys[0]["to"]
        if target_column is None:                 # point at the referenced table's key
            key = self._primary_key(target)
            if len(key) != 1:
                raise ValueError(f"{target} has no single-column key for {table}.{column} to point at")
            target_column = key[0]
        return column, target, target_column

    def _new_row(self, table: str, record: Dict, get_next_id: bool, timestamp: bool, version: bool) -> Dict:
        """The record as a row to insert: real column names, a key, and fresh bookkeeping values."""
        row = self._row(table, record)
        key = self._primary_key(table)
        if len(key) == 1 and row.get(key[0]) is None:
            row.pop(key[0], None)
            # SQLite numbers a column declared INTEGER PRIMARY KEY by itself (it becomes the rowid);
            # any other key needs a value from us.
            if get_next_id or self._key_type(table) != "INTEGER":
                row[key[0]] = self.id(table)
        columns, stamp = self._columns(table), _now()
        if version and "_version" in columns:
            row["_version"] = 1
        for field in ("_created", "_updated"):
            if timestamp and field in columns:
                row[field] = stamp
        return row

    def _write(self, table: str, sql: str, params: list) -> Optional[sqlite3.Cursor]:
        """Run one INSERT or UPDATE. None when a constraint rejects it (logged as a warning)."""
        try:
            with self._connection() as con:
                return con.execute(sql, params)
        except sqlite3.IntegrityError as error:  # duplicate key, NOT NULL, CHECK or FOREIGN KEY
            logger.warning("Write to %s rejected: %s", table, error)
            return None

    def _read_back(self, table: str, row: Dict, rowid: int) -> Optional[Dict]:
        """The row as stored after an insert, found by its key (or by rowid when there is no key)."""
        key = self._primary_key(table)
        if not key:
            rows = self._select(table, "rowid = ?", [rowid])
            return rows[0] if rows else None
        if len(key) == 1:
            return self.find_by_id(table, row.get(key[0], rowid))  # no key given: SQLite assigned the rowid
        return self.find_by_id(table, tuple(row.get(column) for column in key))

    def _remove(self, table: str, where: str, params: list, physical_delete: bool) -> int:
        """DELETE the matching rows, or soft-delete them through _state. Returns how many rows changed."""
        columns = self._columns(table)  # also rejects unknown tables
        if physical_delete:
            sql = f"DELETE FROM {_quote(table)}"
        elif "_state" in columns:
            sql = f"UPDATE {_quote(table)} SET \"_state\" = 'DELETED'"
        else:
            raise ValueError(f"{table} has no _state column to mark rows deleted; "
                             "pass physical_delete=True to remove them")
        if where:
            sql += f" WHERE {where}"
        with self._connection() as con:
            return con.execute(sql, params).rowcount


if __name__ == "__main__":
    logging.basicConfig(format="%(levelname)s %(message)s")
    project_root = Path(__file__).resolve().parents[4]  # impl -> database -> services -> src -> root
    northwind = project_root / "database" / "sqlite" / "northwind.db"
    dao = SqliteDAO(str(northwind))

    print("Tables:", ", ".join(dao.describe()))
    print("\nALFKI:", dao.find_by_id("Customers", "ALFKI", keys=["CompanyName", "City", "Country"]))

    print("\nCustomers in Mexico:")
    for customer in dao.fetch("Customers", query=[("Country", "==", "Mexico")],
                              keys=["CustomerID", "CompanyName"], sort_by=[("CompanyName", 1)]):
        print("   ", customer)

    print("\nOrder 10248, customer expanded:",
          dao.find_by_id("Orders", 10248, keys=["OrderID", "OrderDate", "CustomerID"], expand=["CustomerID"]))
    print("\nOrder Details (10248, 11):", dao.find_by_id("Order Details", (10248, 11)))
    print("\nCompany names containing 'market':",
          [c["CompanyName"] for c in dao.find_by_key_value_like("Customers", "CompanyName", "market")])
    print("\nTop 3 ship countries (raw SQL):", dao.execute_raw_query("Orders", (
        "SELECT ShipCountry, COUNT(*) AS orders FROM Orders GROUP BY ShipCountry ORDER BY orders DESC LIMIT ?",
        [3])))

    # Writes go to a throwaway copy, so northwind.db stays as it is.
    with tempfile.TemporaryDirectory() as folder:
        scratch = SqliteDAO(shutil.copy(northwind, folder))
        category = scratch.insert("Categories", {"CategoryName": "Training", "Description": "Added by the demo"})
        print("\nInserted:", category)
        print("Updated: ", scratch.update("Categories", category["CategoryID"], {"Description": "Changed"}))
        print("Upserted:", scratch.upsert("Customers", {"_id": "TRAIN", "CompanyName": "Training Co."}))
        print("Same key again:", scratch.insert("Customers", {"CustomerID": "TRAIN"}))  # None, plus a warning
        print("Deleted: ", scratch.delete("Customers", "TRAIN", physical_delete=True))
