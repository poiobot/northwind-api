from services.database.dao_interface import DAOInterface
from sqlalchemy import create_engine, MetaData, Table, text, inspect
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Any
from uuid import uuid4
import logging

from api import settings


class SqlDAO(DAOInterface):
    """
    Single DAO implementation for all SQL databases (SQLite, PostgreSQL, MySQL, Oracle)
    using SQLAlchemy Core.
    """

    ops = {
        "==": "=", "!=": "!=", "<": "<", "<=": "<=",
        ">": ">", ">=": ">=", "like": "LIKE",
        "in": "IN", "not-in": "NOT IN"
    }

    def __init__(self, dbname: str, dbtype: str, **credentials):
        self.dbname = dbname
        self.dbtype = dbtype
        connection_string = self._build_connection_string(dbtype, dbname, credentials)
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
               timestamp: bool = True, version: bool = True) -> Dict or None:
        tbl = self._get_table(table)
        pk_col = self._get_pk_column(tbl)

        # Handle id field
        id_val = record.pop("id", None) or record.pop("_id", None) or record.pop(pk_col, None)
        if not id_val:
            id_val = self.id(table)
        record[pk_col] = id_val

        if version:
            record["_version"] = 1
        if timestamp:
            record["_created"] = record["_updated"] = datetime.now(timezone.utc).isoformat()

        try:
            with self.engine.begin() as conn:
                cols = ", ".join(record.keys())
                placeholders = ", ".join(f":{k}" for k in record.keys())
                conn.execute(text(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"), record)
            return record
        except Exception as e:
            logging.warning(f"Insert failed (table={table}): {e}")
            return None

    def upsert(self, table: str, record: Dict, get_next_id: bool = False,
               timestamp: bool = True, version: bool = True) -> Dict or None:
        tbl = self._get_table(table)
        pk_col = self._get_pk_column(tbl)

        id_val = record.pop("id", None) or record.pop("_id", None) or record.pop(pk_col, None)
        if not id_val:
            id_val = self.id(table)
        record[pk_col] = id_val

        try:
            # Check if record exists
            existing = self.find_by_id(table, id_val)

            if existing:
                if timestamp:
                    record["_updated"] = datetime.now(timezone.utc).isoformat()
                    record["_created"] = existing.get("_created", record.get("_updated"))
                if version:
                    record["_version"] = existing.get("_version", 0) + 1

                set_clause = ", ".join(f"{k} = :{k}" for k in record.keys() if k != pk_col)
                record["_pk_val"] = id_val
                with self.engine.begin() as conn:
                    conn.execute(
                        text(f"UPDATE {table} SET {set_clause} WHERE {pk_col} = :_pk_val"),
                        record
                    )
                record.pop("_pk_val", None)
            else:
                if version:
                    record["_version"] = 1
                if timestamp:
                    record["_created"] = record["_updated"] = datetime.now(timezone.utc).isoformat()
                with self.engine.begin() as conn:
                    cols = ", ".join(record.keys())
                    placeholders = ", ".join(f":{k}" for k in record.keys())
                    conn.execute(text(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"), record)

            return record
        except Exception as e:
            logging.error(f"Upsert failed (table={table}): {e}")
            return None

    def update(self, table: str, id: Any, record: Dict, timestamp: bool = True) -> Dict or None:
        tbl = self._get_table(table)
        pk_col = self._get_pk_column(tbl)

        record.pop("_version", None)
        record.pop("_id", None)
        record.pop("id", None)
        if timestamp:
            record["_updated"] = datetime.now(timezone.utc).isoformat()

        try:
            set_clause = ", ".join(f"{k} = :{k}" for k in record.keys() if k != pk_col)
            record["_pk_val"] = id
            with self.engine.begin() as conn:
                conn.execute(
                    text(f"UPDATE {table} SET {set_clause}, _version = _version + 1 WHERE {pk_col} = :_pk_val"),
                    record
                )
            record.pop("_pk_val", None)
            return self.find_by_id(table, id)
        except Exception as e:
            logging.error(f"Update failed (table={table}): {e}")
            return None

    def find_by_id(self, table: str, id: Any, keys: List[str] = "*",
                   expand: List[str or Tuple] = None, meta: Dict = None) -> Dict or None:
        tbl = self._get_table(table)
        pk_col = self._get_pk_column(tbl)

        columns = "*" if keys == "*" else ", ".join(f"{table}.{k}" for k in keys)

        sql = f"SELECT {columns} FROM {table}"

        # Handle expand (JOINs)
        if expand and meta:
            for key in expand:
                if key not in meta.get("references", {}):
                    continue
                ref = meta["references"][key]
                ref_table = ref["table"]
                ref_pk = self._get_pk_column(self._get_table(ref_table))
                sql += f" LEFT JOIN {ref_table} ON {table}.{key} = {ref_table}.{ref_pk}"

        sql += f" WHERE {table}.{pk_col} = :id_val"

        with self.engine.connect() as conn:
            result = conn.execute(text(sql), {"id_val": id})
            row = result.fetchone()
            return self._row_to_dict(row) if row else None

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
        pk_col = self._get_pk_column(tbl)

        columns = "*" if keys == "*" else ", ".join(f"{table}.{k}" for k in keys)
        sql = f"SELECT {columns} FROM {table}"

        # Handle expand (JOINs)
        if expand and meta:
            for key in expand:
                if key not in meta.get("references", {}):
                    continue
                ref = meta["references"][key]
                ref_table = ref["table"]
                ref_pk = self._get_pk_column(self._get_table(ref_table))
                sql += f" LEFT JOIN {ref_table} ON {table}.{key} = {ref_table}.{ref_pk}"

        # Build WHERE clause
        params = {}
        query = query or []
        if query:
            conditions = []
            for i, (key, op, value) in enumerate(query):
                param_name = f"p{i}"
                sql_op = self.ops.get(op.lower(), "=")

                # Remap _id to actual pk column
                col = pk_col if key == "_id" else key

                if sql_op == "IN":
                    placeholders = ", ".join(f":p{i}_{j}" for j in range(len(value)))
                    conditions.append(f"{table}.{col} IN ({placeholders})")
                    for j, v in enumerate(value):
                        params[f"p{i}_{j}"] = v
                elif sql_op == "NOT IN":
                    placeholders = ", ".join(f":p{i}_{j}" for j in range(len(value)))
                    conditions.append(f"{table}.{col} NOT IN ({placeholders})")
                    for j, v in enumerate(value):
                        params[f"p{i}_{j}"] = v
                elif sql_op == "LIKE":
                    conditions.append(f"{table}.{col} LIKE :{param_name}")
                    params[param_name] = f"%{value}%"
                else:
                    conditions.append(f"{table}.{col} {sql_op} :{param_name}")
                    params[param_name] = value

            sql += " WHERE " + " AND ".join(conditions)

        # ORDER BY
        if sort_by:
            order_parts = []
            for col, direction in sort_by:
                if direction in [-1, 1]:
                    order_parts.append(f"{col} {'ASC' if direction == 1 else 'DESC'}")
            if order_parts:
                sql += " ORDER BY " + ", ".join(order_parts)

        with self.engine.connect() as conn:
            result = conn.execute(text(sql), params)
            return [self._row_to_dict(row) for row in result]

    def delete(self, table: str, id: Any, physical_delete: bool = True) -> bool:
        tbl = self._get_table(table)
        pk_col = self._get_pk_column(tbl)

        with self.engine.begin() as conn:
            if physical_delete:
                result = conn.execute(
                    text(f"DELETE FROM {table} WHERE {pk_col} = :id_val"),
                    {"id_val": id}
                )
                return result.rowcount > 0
            else:
                result = conn.execute(
                    text(f"UPDATE {table} SET _state = 'DELETED' WHERE {pk_col} = :id_val"),
                    {"id_val": id}
                )
                return result.rowcount > 0

    def delete_objects_list(self, table: str, ids: List, physical_delete: bool = True) -> int:
        tbl = self._get_table(table)
        pk_col = self._get_pk_column(tbl)
        params = {f"id_{i}": v for i, v in enumerate(ids)}
        placeholders = ", ".join(f":id_{i}" for i in range(len(ids)))

        with self.engine.begin() as conn:
            if physical_delete:
                result = conn.execute(
                    text(f"DELETE FROM {table} WHERE {pk_col} IN ({placeholders})"), params
                )
            else:
                result = conn.execute(
                    text(f"UPDATE {table} SET _state = 'DELETED' WHERE {pk_col} IN ({placeholders})"), params
                )
            return result.rowcount

    def delete_many(self, table: str, query: List[Tuple] = None, physical_delete: bool = False) -> int:
        tbl = self._get_table(table)
        pk_col = self._get_pk_column(tbl)
        query = query or []

        params = {}
        conditions = []
        for i, (key, op, value) in enumerate(query):
            sql_op = self.ops.get(op.lower(), "=")
            col = pk_col if key == "_id" else key
            param_name = f"p{i}"
            if sql_op == "LIKE":
                conditions.append(f"{col} LIKE :{param_name}")
                params[param_name] = f"%{value}%"
            else:
                conditions.append(f"{col} {sql_op} :{param_name}")
                params[param_name] = value

        where = " WHERE " + " AND ".join(conditions) if conditions else ""

        with self.engine.begin() as conn:
            if physical_delete:
                result = conn.execute(text(f"DELETE FROM {table}{where}"), params)
            else:
                result = conn.execute(
                    text(f"UPDATE {table} SET _state = 'DELETED'{where}"), params
                )
            return result.rowcount

    def delete_all(self, table: str, physical_delete: bool = False) -> int:
        with self.engine.begin() as conn:
            if physical_delete:
                result = conn.execute(text(f"DELETE FROM {table}"))
            else:
                result = conn.execute(text(f"UPDATE {table} SET _state = 'DELETED'"))
            return result.rowcount

    def distinct(self, table: str, key: str, query: List[Tuple] = []) -> List[Any]:
        tbl = self._get_table(table)
        pk_col = self._get_pk_column(tbl)

        sql = f"SELECT DISTINCT {key} FROM {table}"
        params = {}

        if query:
            conditions = []
            for i, (k, v) in enumerate(query):
                col = pk_col if k == "_id" else k
                conditions.append(f"{col} = :p{i}")
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
