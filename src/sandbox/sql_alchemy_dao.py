"""
Minimal SqlAlchemyDAO for the sandbox: only find_by_id is implemented, with SQLAlchemy Core, so the
same code works on SQLite, PostgreSQL, MySQL...: only the URL given to the constructor changes.
Every other DAOInterface method is a stub that returns None.

Needs SQLAlchemy:   pip install sqlalchemy
Run from anywhere:  python src/sandbox/sql_alchemy_dao.py
"""
from pathlib import Path
from typing import Dict, List, Tuple, Any

from sqlalchemy import MetaData, Table, create_engine, select

from dao_interface import DAOInterface


class SqlAlchemyDAO(DAOInterface):

    def __init__(self, url: str):
        # A database URL, e.g. "sqlite:///database/sqlite/northwind.db" or
        # "postgresql://user:password@localhost/northwind". The engine opens connections when needed.
        self.engine = create_engine(url)

    def describe(self) -> Dict:
        return None

    def id(self, table: str=None) -> str:
        return None

    def insert(self, table: str, record: Dict, get_next_id: bool=False, timestamp: bool = True, version: bool = True) -> Dict or None:
        return None

    def upsert(self, table: str, record: Dict, get_next_id: bool = False, timestamp: bool = True, version: bool = True) -> Dict or None:
        return None

    def update(self, table: str, id: Any, record: Dict, timestamp: bool = True) -> Dict or None:
        return None

    def find_by_id(self, table: str, id: Any, keys: List[str] = "*", expand: List[str or Tuple] = None, meta: Dict=None) -> Dict:
        """
        Locates a record by its primary key and returns it as a dict, or None if there is no such row.
        A composite key takes a tuple, e.g. find_by_id("Order Details", (10248, 11)) for OrderID 10248, ProductID 11.
        Use the table's exact name ("Customers", not "customers"): on SQLite, SQLAlchemy finds the primary
        key only under the exact name.
        expand and meta are not supported yet and are ignored.
        """
        # 1. Ask the database to describe the table. Reflection (autoload_with) reads its columns and primary
        #    key from whatever database the engine points at. An unknown table raises NoSuchTableError.
        tbl = Table(table, MetaData(), autoload_with=self.engine)

        # 2. Find the primary key: reflection has already read it.
        key = list(tbl.primary_key.columns)
        if not key:
            raise ValueError(f"{table} has no primary key")
        values = list(id) if isinstance(id, (tuple, list)) else [id]
        if len(values) != len(key):
            raise ValueError(f"{table} is keyed by {[column.name for column in key]}: pass one value per key column")

        # 3. Choose the columns to return. No manual check needed: tbl.c[name] only knows the table's real
        #    columns and raises KeyError for any other name.
        selected = [tbl] if keys == "*" else [tbl.c[name] for name in keys]

        # 4. Build the query from Python objects. SQLAlchemy writes the SQL for this database, quotes the
        #    names and sends the values as parameters.
        query = select(*selected).where(*[column == value for column, value in zip(key, values)])
        with self.engine.connect() as con:  # the connection goes back to the engine's pool afterwards
            row = con.execute(query).mappings().first()
        return dict(row) if row else None

    def find_objects_list(self, table: str, ids: List, expand: List[str] = None, keys: List[str] = "*", meta: Dict=None) -> List[Any]:
        return None

    def find_by_key_value(self, table: str, key: str, op: str="==", value: Any = None, expand: List[str] = None, keys: List[str] = "*", meta: Dict=None) -> List[Dict]:
        return None

    def find_by_key_value_like(self, table: str, key: str, value: Any, expand: List[str] = None, keys: List[str] = "*", meta: Dict=None) -> List[Dict]:
        return None

    def fetch(self, table: str, query: List[Tuple] = None, expand: List[str] = None, keys: List[str] = "*", sort_by: List[Tuple[str,int]]=None, meta: Dict=None) -> List[Dict]:
        return None

    def delete(self, table: str, id: Any, physical_delete: bool=False) -> bool:
        return None

    def delete_objects_list(self, table: str, ids: List, physical_delete: bool=False) -> int:
        return None

    def delete_many(self, table: str, query: List[Tuple] or None, physical_delete: bool=False) -> int:
        return None

    def delete_all(self, table: str, physical_delete: bool=False) -> int:
        return None

    def distinct(self, table: str, key: str, query: List[Tuple] = []) -> List[Any]:
        return None

    def execute_raw_query(self, table: str, query: Tuple[str, Dict or List]) -> Any:
        return None


if __name__ == "__main__":
    northwind = Path(__file__).resolve().parents[2] / "database" / "sqlite" / "northwind.db"
    dao = SqlAlchemyDAO(f"sqlite:///{northwind}")  # another database only needs another URL
    print(dao.find_by_id("Customers", "ALFKI", keys=["CustomerID", "CompanyName", "City"]))            # text key
    print(dao.find_by_id("Orders", 10248, keys=["OrderID", "CustomerID", "OrderDate"]))  # integer key
    print(dao.find_by_id("Order Details", (10248, 11)))                                   # composite key
    print(dao.find_by_id("Customers", "NOPE!"))                                           # no such row
