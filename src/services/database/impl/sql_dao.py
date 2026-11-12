from services.database.dao_interface import DAOInterface
from sqlalchemy import create_engine, MetaData, Table, text, inspect, and_, or_, Integer
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Any
from uuid import uuid4

from api import settings


class SqlDAO(DAOInterface):
    """
    Single DAO implementation for all SQL databases (SQLite, PostgreSQL, MySQL, Oracle)
    using SQLAlchemy Core.

    Works on Spore-shaped tables (a text _id plus _version/_created/_updated/_state) and on
    plain schemas: integer keys the database assigns, composite keys, names that need
    quoting, and no bookkeeping columns. Bookkeeping is written only where its column exists.
    """

    ops = {
        "==": "=", "!=": "!=", "<": "<", "<=": "<=",
        ">": ">", ">=": ">=", "like": "LIKE",
        "in": "IN", "not-in": "NOT IN"
    }

    bookkeeping = ("_version", "_created", "_updated", "_state")

    def __init__(self, dbname: str, dbtype: str, **credentials):
        self.dbname = dbname
        self.dbtype = dbtype.lower()
        connection_string = self._build_connection_string(self.dbtype, dbname, credentials)
        self.engine = create_engine(connection_string)
        self.metadata = MetaData()

    def _build_connection_string(self, dbtype: str, dbname: str, credentials: dict) -> str:
        """Build SQLAlchemy connection string from settings or credentials."""
        # Settings-level connection string takes precedence
        if hasattr(settings, 'DB_CONNECTION_STRING') and settings.DB_CONNECTION_STRING:
            return settings.DB_CONNECTION_STRING

        host = getattr(settings, 'DB_HOST', 'localhost') or 'localhost'
        port = getattr(settings, 'DB_PORT', None)
        user = getattr(settings, 'DB_USER', None)
        password = getattr(settings, 'DB_PASSWORD', None)

        # Override with credentials dict if provided
        host = credentials.get('host', host)
        port = credentials.get('port', port)
        user = credentials.get('user', user)
        password = credentials.get('password', password)

        match dbtype:
            case 'sqlite' | 'sqlite3':
                return f"sqlite:///{dbname}"
            case 'postgres':
                port = port or '5432'
                auth = f"{user}:{password}@" if user else ""
                return f"postgresql://{auth}{host}:{port}/{dbname}"
            case 'mysql':
                port = port or '3306'
                auth = f"{user}:{password}@" if user else ""
                return f"mysql+pymysql://{auth}{host}:{port}/{dbname}"
            case 'oracle':
                port = port or '1521'
                auth = f"{user}:{password}@" if user else ""
                return f"oracle+oracledb://{auth}{host}:{port}/{dbname}"
            case _:
                raise ValueError(f"Unsupported database type: {dbtype}")

    def _get_table(self, table_name: str) -> Table:
        """Reflect a table from the database."""
        if table_name not in self.metadata.tables:
            Table(table_name, self.metadata, autoload_with=self.engine)
        return self.metadata.tables[table_name]

    def _get_pk_column(self, table: Table) -> str:
        """Get the primary key column name for a table."""
        pk_cols = [c.name for c in table.primary_key.columns]
        return pk_cols[0] if pk_cols else '_id'

    def _row_to_dict(self, row) -> Dict:
        """Convert a SQLAlchemy Row to a dictionary."""
        return dict(row._mapping)

    def _q(self, name: str) -> str:
        """Quote an identifier the way this dialect needs it (spaces, reserved words, mixed case)."""
        return self.engine.dialect.identifier_preparer.quote(name)

    def _key_columns(self, table: Table) -> List[str]:
        """Primary key columns, or ['_id'] for a table without a primary key."""
        return [c.name for c in table.primary_key.columns] or ['_id']

    def _key_items(self, table: Table, id: Any) -> List[Tuple[str, Any]]:
        """(column, value) pairs for a row's whole primary key.

        A composite key takes a dict or a tuple; a single value would match several rows.
        """
        cols = self._key_columns(table)
        if isinstance(id, dict):
            missing = [c for c in cols if c not in id]
            if missing:
                raise ValueError(f"{table.name} key is ({', '.join(cols)}); missing {', '.join(missing)}")
            return [(c, id[c]) for c in cols]
        if isinstance(id, (tuple, list)):
            if len(id) != len(cols):
                raise ValueError(f"{table.name} key is ({', '.join(cols)}); got {len(id)} values")
            return list(zip(cols, id))
        if len(cols) > 1:
            raise ValueError(f"{table.name} has a composite primary key ({', '.join(cols)}); "
                             f"pass the id as a dict or a tuple")
        return [(cols[0], id)]

    def _key_clause(self, table: Table, id: Any):
        return and_(*(table.c[col] == value for col, value in self._key_items(table, id)))

    def _column(self, table: Table, key: str) -> str:
        """The column a query key names; '_id' stands for the primary key."""
        if key != "_id":
            return key
        cols = self._key_columns(table)
        if len(cols) > 1:
            raise ValueError(f"{table.name} has a composite primary key ({', '.join(cols)}); "
                             f"'_id' can't stand for it")
        return cols[0]

    def _drop_absent_bookkeeping(self, table: Table, record: Dict) -> Dict:
        """Copy of record without the Spore bookkeeping fields this table has no column for."""
        return {k: v for k, v in record.items() if k not in self.bookkeeping or k in table.c}

    def _resolve_id(self, table: Table, record: Dict) -> Dict:
        """Copy of record ready to write: absent bookkeeping dropped, and an 'id'/'_id' alias
        moved onto the key column(s)."""
        record = self._drop_absent_bookkeeping(table, record)
        key_cols = [c.name for c in table.primary_key.columns]
        given = None
        for alias in ("id", "_id"):
            if alias in record and alias not in key_cols:
                value = record.pop(alias)
                if given in (None, ""):
                    given = value
        if given not in (None, ""):
            record.update(self._key_items(table, given))
        return record

    def _require_state(self, table: Table):
        if "_state" not in table.c:
            raise ValueError(f"{table.name} has no _state column to soft-delete with; use physical_delete=True")

    def _delete_statement(self, table: Table, physical_delete: bool):
        """DELETE, or the soft delete that marks _state as DELETED."""
        if physical_delete:
            return table.delete()
        self._require_state(table)
        return table.update().values(_state="DELETED")

    def describe(self) -> Dict:
        inspector = inspect(self.engine)
        result = {}
        for table_name in inspector.get_table_names():
            columns = inspector.get_columns(table_name)
            result[table_name] = {
                col['name']: str(col['type']) for col in columns
            }
        return result

    def id(self, table: str = None) -> str:
        return str(uuid4())

    def insert(self, table: str, record: Dict, get_next_id: bool = False,
               timestamp: bool = True, version: bool = True) -> Dict:
        tbl = self._get_table(table)
        record = self._resolve_id(tbl, record)

        # A single key left empty: the database numbers integer keys; text keys get a UUID
        numbered_by_db = None
        key_cols = self._key_columns(tbl)
        if len(key_cols) == 1 and key_cols[0] in tbl.c and record.get(key_cols[0]) in (None, ""):
            key = key_cols[0]
            record.pop(key, None)
            if isinstance(tbl.c[key].type, Integer):
                numbered_by_db = key
            else:
                record[key] = self.id(table)

        if version and "_version" in tbl.c:
            record["_version"] = 1
        if timestamp:
            now = datetime.now(timezone.utc).isoformat()
            for col in ("_created", "_updated"):
                if col in tbl.c:
                    record[col] = now

        with self.engine.begin() as conn:
            result = conn.execute(tbl.insert().values(record))
            if numbered_by_db:
                record[numbered_by_db] = result.inserted_primary_key[0]
        return record

    def upsert(self, table: str, record: Dict, get_next_id: bool = False,
               timestamp: bool = True, version: bool = True) -> Dict:
        tbl = self._get_table(table)
        record = self._resolve_id(tbl, record)

        key_cols = self._key_columns(tbl)
        key = {c: record[c] for c in key_cols if record.get(c) not in (None, "")}
        existing = self.find_by_id(table, key) if len(key) == len(key_cols) else None
        if existing is None:
            return self.insert(table, record, timestamp=timestamp, version=version)

        now = datetime.now(timezone.utc).isoformat()
        if timestamp and "_updated" in tbl.c:
            record["_updated"] = now
        if timestamp and "_created" in tbl.c:
            record["_created"] = existing.get("_created") or now
        if version and "_version" in tbl.c:
            record["_version"] = (existing.get("_version") or 0) + 1

        values = {k: v for k, v in record.items() if k not in key}
        if values:
            with self.engine.begin() as conn:
                conn.execute(tbl.update().where(self._key_clause(tbl, key)).values(values))
        return record

    def update(self, table: str, id: Any, record: Dict, timestamp: bool = True) -> Dict or None:
        tbl = self._get_table(table)
        key = dict(self._key_items(tbl, id))

        values = {k: v for k, v in self._drop_absent_bookkeeping(tbl, record).items()
                  if k not in ("id", "_id", "_version") and k not in key}
        if timestamp and "_updated" in tbl.c:
            values["_updated"] = datetime.now(timezone.utc).isoformat()
        if "_version" in tbl.c:
            values["_version"] = tbl.c["_version"] + 1

        if values:
            with self.engine.begin() as conn:
                conn.execute(tbl.update().where(self._key_clause(tbl, key)).values(values))
        return self.find_by_id(table, id)

    def find_by_id(self, table: str, id: Any, keys: List[str] = "*",
                   expand: List[str or Tuple] = None, meta: Dict = None) -> Dict or None:
        tbl = self._get_table(table)
        query = [(col, "==", value) for col, value in self._key_items(tbl, id)]
        found = self.fetch(table, query=query, keys=keys, expand=expand, meta=meta)
        return found[0] if found else None

    def find_objects_list(self, table: str, ids: List, expand: List[str] = None,
                         keys: List[str] = "*", meta: Dict = None) -> List[Dict]:
        return self.fetch(table=table, query=[("_id", "in", ids)], keys=keys, expand=expand, meta=meta)

    def find_by_key_value(self, table: str, key: str, op: str = "==", value: Any = None,
                          expand: List[str] = None, keys: List[str] = "*",
                          meta: Dict = None) -> List[Dict]:
        return self.fetch(table=table, query=[(key, op, value)], expand=expand, keys=keys, meta=meta)

    def find_by_key_value_like(self, table: str, key: str, value: Any,
                               expand: List[str] = None, keys: List[str] = "*",
                               meta: Dict = None) -> List[Dict]:
        return self.fetch(table=table, query=[(key, "like", value)], expand=expand, keys=keys, meta=meta)

    def fetch(self, table: str, query: List[Tuple] = None, expand: List[str] = None,
              keys: List[str] = "*", sort_by: List[Tuple[str, int]] = None,
              meta: Dict = None) -> List[Dict]:
        tbl = self._get_table(table)
        t = self._q(table)

        columns = "*" if keys == "*" else ", ".join(f"{t}.{self._q(k)}" for k in keys)
        sql = f"SELECT {columns} FROM {t}"

        # Handle expand (JOINs)
        if expand and meta:
            for key in expand:
                if key not in meta.get("references", {}):
                    continue
                ref = meta["references"][key]
                ref_table = ref["table"]
                ref_pk = self._get_pk_column(self._get_table(ref_table))
                r = self._q(ref_table)
                sql += f" LEFT JOIN {r} ON {t}.{self._q(key)} = {r}.{self._q(ref_pk)}"

        # Build WHERE clause
        params = {}
        query = query or []
        if query:
            conditions = []
            for i, (key, op, value) in enumerate(query):
                param_name = f"p{i}"
                sql_op = self.ops.get(op.lower(), "=")

                # _id stands for the table's key column
                col = f"{t}.{self._q(self._column(tbl, key))}"

                if sql_op == "IN":
                    placeholders = ", ".join(f":p{i}_{j}" for j in range(len(value)))
                    conditions.append(f"{col} IN ({placeholders})")
                    for j, v in enumerate(value):
                        params[f"p{i}_{j}"] = v
                elif sql_op == "NOT IN":
                    placeholders = ", ".join(f":p{i}_{j}" for j in range(len(value)))
                    conditions.append(f"{col} NOT IN ({placeholders})")
                    for j, v in enumerate(value):
                        params[f"p{i}_{j}"] = v
                elif sql_op == "LIKE":
                    conditions.append(f"{col} LIKE :{param_name}")
                    params[param_name] = f"%{value}%"
                else:
                    conditions.append(f"{col} {sql_op} :{param_name}")
                    params[param_name] = value

            sql += " WHERE " + " AND ".join(conditions)

        # ORDER BY
        if sort_by:
            order_parts = []
            for col, direction in sort_by:
                if direction in [-1, 1]:
                    order_parts.append(f"{self._q(col)} {'ASC' if direction == 1 else 'DESC'}")
            if order_parts:
                sql += " ORDER BY " + ", ".join(order_parts)

        with self.engine.connect() as conn:
            result = conn.execute(text(sql), params)
            return [self._row_to_dict(row) for row in result]

    def delete(self, table: str, id: Any, physical_delete: bool = True) -> bool:
        tbl = self._get_table(table)
        where = self._key_clause(tbl, id)
        statement = self._delete_statement(tbl, physical_delete)

        with self.engine.begin() as conn:
            return conn.execute(statement.where(where)).rowcount > 0

    def delete_objects_list(self, table: str, ids: List, physical_delete: bool = True) -> int:
        tbl = self._get_table(table)
        if not ids:
            return 0
        key_cols = self._key_columns(tbl)
        if len(key_cols) == 1 and not any(isinstance(i, (dict, tuple, list)) for i in ids):
            where = tbl.c[key_cols[0]].in_(ids)
        else:
            where = or_(*(self._key_clause(tbl, i) for i in ids))
        statement = self._delete_statement(tbl, physical_delete)

        with self.engine.begin() as conn:
            return conn.execute(statement.where(where)).rowcount

    def delete_many(self, table: str, query: List[Tuple] = None, physical_delete: bool = False) -> int:
        tbl = self._get_table(table)
        t = self._q(table)
        query = query or []

        params = {}
        conditions = []
        for i, (key, op, value) in enumerate(query):
            sql_op = self.ops.get(op.lower(), "=")
            col = self._q(self._column(tbl, key))
            param_name = f"p{i}"
            if sql_op == "LIKE":
                conditions.append(f"{col} LIKE :{param_name}")
                params[param_name] = f"%{value}%"
            else:
                conditions.append(f"{col} {sql_op} :{param_name}")
                params[param_name] = value

        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        if not physical_delete:
            self._require_state(tbl)

        with self.engine.begin() as conn:
            if physical_delete:
                result = conn.execute(text(f"DELETE FROM {t}{where}"), params)
            else:
                result = conn.execute(
                    text(f"UPDATE {t} SET _state = 'DELETED'{where}"), params
                )
            return result.rowcount

    def delete_all(self, table: str, physical_delete: bool = False) -> int:
        t = self._q(table)
        if not physical_delete:
            self._require_state(self._get_table(table))

        with self.engine.begin() as conn:
            if physical_delete:
                result = conn.execute(text(f"DELETE FROM {t}"))
            else:
                result = conn.execute(text(f"UPDATE {t} SET _state = 'DELETED'"))
            return result.rowcount

    def distinct(self, table: str, key: str, query: List[Tuple] = []) -> List[Any]:
        tbl = self._get_table(table)

        sql = f"SELECT DISTINCT {self._q(key)} FROM {self._q(table)}"
        params = {}

        if query:
            conditions = []
            for i, (k, v) in enumerate(query):
                conditions.append(f"{self._q(self._column(tbl, k))} = :p{i}")
                params[f"p{i}"] = v
            sql += " WHERE " + " AND ".join(conditions)

        with self.engine.connect() as conn:
            result = conn.execute(text(sql), params)
            return [row[0] for row in result]

    def execute_raw_query(self, table: str, query: Tuple[str, Dict or List]) -> Any:
        operation = query[0]
        sql_text = query[1]
        params = query[2] if len(query) > 2 else {}

        with self.engine.connect() as conn:
            result = conn.execute(text(sql_text), params)
            if operation in ("select", "find"):
                return [self._row_to_dict(row) for row in result]
            return result
