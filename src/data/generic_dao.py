from services.database.database_connection_manager import DatabaseConnectionManager
from lib.pydantic_scheme_extractor import SchemeExtractor, BaseModel
from typing import List, Dict, Union, Tuple, Any
from api import settings


class GenericDAO:

    def __init__(self, dbtype=settings.DBTYPE, dbname=settings.DBNAME):
        self.dbname = dbname
        self.handler = DatabaseConnectionManager().connect(dbtype=dbtype, dbname=dbname)

    def describe(self, entity: BaseModel):
        return SchemeExtractor.extract_class_scheme(entity)
    
    def table(self, entity: BaseModel):
        return self.describe(entity)["table"]

    def id(self, entity: BaseModel):
        return self.handler.id(table=self.table(entity))

    def insert(self, entity: BaseModel, data: Any, reify: bool=True) -> Any:
        # by_alias: the domain models alias id/version/created/updated to
        # _id/_version/_created/_updated. Dumping without it writes BOTH
        # forms into the document — the handler adds the underscored ones —
        # which then pollutes the sample Spore infers the next model from.
        if isinstance(data, BaseModel): data = data.model_dump(by_alias=True)
        result = self.handler.insert(table=self.table(entity), record=data)
        return None if not result else entity(**result) if reify else result

    def upsert(self, entity: BaseModel, data: Any, reify: bool=True) -> Any:
        # by_alias: the domain models alias id/version/created/updated to
        # _id/_version/_created/_updated. Dumping without it writes BOTH
        # forms into the document — the handler adds the underscored ones —
        # which then pollutes the sample Spore infers the next model from.
        if isinstance(data, BaseModel): data = data.model_dump(by_alias=True)
        result = self.handler.upsert(table=self.table(entity), record=data)
        return None if not result else entity(**result) if reify else result

    def update(self, entity: BaseModel, id: Any, data: Any, reify: bool=True) -> Any:
        # by_alias: the domain models alias id/version/created/updated to
        # _id/_version/_created/_updated. Dumping without it writes BOTH
        # forms into the document — the handler adds the underscored ones —
        # which then pollutes the sample Spore infers the next model from.
        if isinstance(data, BaseModel): data = data.model_dump(by_alias=True)
        result = self.handler.update(table=self.table(entity), id=id, record=data)
        if not result:
            return None
        return entity(**result) if reify else result

    def find_by_id(self, entity: BaseModel, id: str, keys: List[str]= "*", expand: List[str]=None, reify: bool=True) -> Any:
        meta = self.describe(entity)
        result = self.handler.find_by_id(table=meta["table"], id=id, keys=keys, expand=expand, meta=meta)
        return None if not result else entity(**result) if reify else result

    def find_list(self, entity: BaseModel, ids: List[Any], keys: List[str]= "*", expand: List[str]=None, reify: bool=True) -> List[Any]:
        meta = self.describe(entity)
        result_set = self.handler.find_objects_list(table=meta["table"], ids=ids, keys=keys, expand=expand, meta=meta)
        for record in result_set:
            yield entity(**record) if reify else record

    def find_by_key_value(self, entity: BaseModel, key: str, value: Any, keys: List[str]="*", reify: bool=True) -> List[Any]:
        meta = self.describe(entity)
        result_set = self.handler.find_by_key_value(table=meta["table"], key=key, value=value, keys=keys, meta=meta)
        for record in result_set:
            yield entity(**record) if reify else record

    def find_by_key_value_like(self, entity: BaseModel, key: str, value: Any, keys: List[str]="*", reify: bool=True) -> List[Any]:
        meta = self.describe(entity)
        result_set = self.handler.find_by_key_value_like(table=meta["table"], key=key, value=value, keys=keys, meta=meta)
        for record in result_set:
            yield entity(**record) if reify else record

    def fetch(self, entity: BaseModel, query: List[Tuple]=None, expand: List[str]=None, keys: List[str]="*", sort_by: List[Tuple[str,int]]=None, reify: bool=True) -> List[Any]:
        meta = self.describe(entity)
        result_set = self.handler.fetch(table=meta["table"], query=query, keys=keys, sort_by=sort_by, expand=expand, meta=meta)
        for record in result_set:
            yield entity(**record) if reify else record

    def delete(self, entity: BaseModel, id: str, physical_delete: bool=True) -> bool:
        return self.handler.delete(table=self.table(entity), id=id, physical_delete=physical_delete)

    def delete_objects_list(self, entity: BaseModel, ids: List[str], physical_deletion: bool=True) -> int:
        return self.handler.delete_objects_list(table=self.table(entity), ids=ids, physical_delete=physical_deletion)

    def delete_many(self, entity: BaseModel, query: List[Tuple] = None, physical_delete: bool = False) -> int:
        return self.handler.delete_many(table=self.table(entity), query=query, physical_delete=physical_delete)

    def delete_all(self, entity: BaseModel, physical_deletion: bool=False) -> int:
        return self.handler.delete_all(table=self.table(entity), physical_delete=physical_deletion)

    def distinct(self, table: str, key: str, query: List[Tuple] = []) -> List[Any]:
        """
        Retrieves the set of unique values from a field within a table
        :param table: name of table/collection
        :param key: name of field within table (column)
        :param query: List of tuples containing AND conditions; [('name', 'Josh'), ('lastname','Linforth')]
        :return: List of unique values of key within collection
        """
        pass

    def execute_raw_query(self, table: str, query: Tuple[str, Dict or List]) -> Any:
        """
        Allows execution of a low level query
        :param table: name of the table/collection
        :param query: a structure describing the query to execute
        :return: The type depends on the query
        """
        pass


if __name__ == "__main__":

    from domain.customer import Customer

    dao = GenericDAO()  # DBTYPE and DBNAME come from the project's .env, through api.settings

    print(dao.find_by_id(entity=Customer, id="ALFKI"))
