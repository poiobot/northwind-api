from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Any


class DAOInterface(ABC):

    @abstractmethod
    def describe(self) -> Dict:
        """
        Retrieves database metadata
        :return: dictionary of tables and their attributes
        """

    @abstractmethod
    def id(self, table: str=None) -> str:
        """
        Infers a unique id to be used to insert a new document in a collection
        :param table: name of the table
        :return: the next id to ve used according to context
        """

    @abstractmethod
    def insert(self, table: str, record: Dict, get_next_id: bool=False, timestamp: bool = True, version: bool = True) -> Dict or None:
        """
        Inserts a single document in the target table/collection
        :param table: name of the table/collection
        :param record: record to insert
        :param timestamp: whether to insert timestamp or not
        :param version: whether to insert version or not
        :return: the inserted record as a dictionary
        """

    @abstractmethod
    def upsert(self, table: str, record: Dict, get_next_id: bool = False, timestamp: bool = True, version: bool = True) -> Dict or None:
        """
        Upserts a single document in the target table/collection.
        If the document exists, it is replaced. Otherwise, it is inserted.
        :param table: name of the table/collection
        :param record: record to upsert
        :param get_next_id: whether to generate a custom next ID
        :param timestamp: whether to include created/updated timestamps
        :param version: whether to include a version field
        :return: the upserted document
        """

    @abstractmethod
    def update(self, table: str, id: Any, record: Dict, timestamp: bool = True) -> Dict or None:
        """
        Updates a record with the newest info provided
        :param table: name of the table/collection
        :param id: unique id identifying the record to update
        :param record: dictionary with fields to update
        :param timestamp: whether to insert timestamp or not
        :return: the updated record as a Dict
        """

    @abstractmethod
    def find_by_id(self, table: str, id: Any, keys: List[str] = "*", expand: List[str or Tuple] = None, meta: Dict=None) -> Dict:
        """
        Locates a record within a table/collection using its unique ID
        :param table: name of the table/collection to search
        :param id: unique id identifying the record
        :param keys: list of fields to retrieve
        :param expand: list of fields to expand as objects
        :return: The record, if found, None otherwise
        """

    @abstractmethod
    def find_objects_list(self, table: str, ids: List, expand: List[str] = None, keys: List[str] = "*", meta: Dict=None) -> List[Any]:
        """
        Given a list of ids, retrieve corresponding records within table/collection
        :param table: name of the table/collection
        :param ids: list of ids
        :param keys List of fields to retrieve
        """

    @abstractmethod
    def find_by_key_value(self, table: str, key: str, op: str="==", value: Any = None, expand: List[str] = None, keys: List[str] = "*", meta: Dict=None) -> List[Dict]:
        """
        Retrieves a set of records which match a specific condition using a ket-value pair
        :param table: name of the table/collection for search
        :param key: name of the search key
        :param value: value to match the key
        :param op: comparison operator (==, !=, >, >=, <, <=)
        :param keys: list of fields to retrieve, all if not specified
        :return: a list of matching records or empty list if not found
        """

    @abstractmethod
    def find_by_key_value_like(self, table: str, key: str, value: Any, expand: List[str] = None, keys: List[str] = "*", meta: Dict=None) -> List[Dict]:
        """
        Retrieves a set of records which loosely match a specific condition using a ket-value pair
        :param table: name of the table/collection for search
        :param key: name of the search key
        :param value: value contained in the key (substring)
        :param keys: list of fields to retrieve, all if not specified
        :return: a list of matching records or empty list if not found
        """

    @abstractmethod
    def fetch(self, table: str, query: List[Tuple] = None, expand: List[str] = None, keys: List[str] = "*", sort_by: List[Tuple[str,int]]=None, meta: Dict=None) -> List[Dict]:
        """
        Returns all records within a table/collection
        :param table: Table name
        :param query: List of (key,value,op) tuples representing ANDed conditions (op might be ==, >, >= ...)
        :param expand: List of references to reify
        :param keys: list of fields to return, if not specified, returns all fields
        :return: All records from table/collection
        """

    @abstractmethod
    def delete(self, table: str, id: Any, physical_delete: bool=False) -> bool:
        """
        Deletes a record from a table/collection given a valid id
        :param table: Name of the table/collection
        :param id: Valid id
        :param physical_delete: whether to delete the record or not
        :return: True if record exists, False otherwise
        """

    @abstractmethod
    def delete_objects_list(self, table: str, ids: List, physical_delete: bool=False) -> int:
        """
        Given a list of ids, delete corresponding records within table/collection
        :param table: name of the table/collection
        :param ids: list of ids
        :return: Number of deleted records
        """

    @abstractmethod
    def delete_many(self, table: str, query: List[Tuple] or None, physical_delete: bool=False) -> int:
        """
        Given a list of ids, delete corresponding records within table/collection
        :param table: name of the table/collection
        :param ids: list of ids
        :return: Number of deleted records
        """

    @abstractmethod
    def delete_all(self, table: str, physical_delete: bool=False) -> int:
        """
        Delete table/collection
        :param table: name of the table/collection
        :return: Returns the number of deleted records
        """

    @abstractmethod
    def distinct(self, table: str, key: str, query: List[Tuple] = []) -> List[Any]:
        """
        Retrieves the set of unique values from a field within a table
        :param table: name of table/collection
        :param key: name of field within table (column)
        :param query: List of tuples containing AND conditions; [('name', 'Josh'), ('lastname','Linforth')]
        :return: List of unique values of key within collection
        """

    @abstractmethod
    def execute_raw_query(self, table: str, query: Tuple[str, Dict or List]) -> Any:
        """
        Allows execution of a low level query
        :param table: name of the table/collection
        :param query: a structure describing the query to execute
        :return: The type depends on the query
        """


class IDatabaseService(ABC):

    @abstractmethod
    def connect(self, dbtype: str, dbname: str, **credentials) -> DAOInterface:
        """
        Returns a data access object connected to a specific database
        """