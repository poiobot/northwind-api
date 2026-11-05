from services.database.dao_interface import DAOInterface
from pymongo import MongoClient, ReturnDocument
import pymongo.errors
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Any
from bson import ObjectId
import logging
import json
import re

from api import settings

class MongoDAO(DAOInterface):
    metadata = None
    ops = {
        "==": "$eq", "!=": "$ne", "<": "$lt", "<=": "$lte", ">": "$gt", ">=": "$gte", 
        "in": "$in", "not-in": "$nin", "all-in": "$all", "like": "$regex"
    }

    def __init__(self, dbname: str, **credentials):
        self.dbname = dbname
        self.handler = MongoClient(settings.MONGO_SERVER)
        self.db = self.handler[dbname]

    def _filter(self, query: List[Tuple]) -> Dict:
        """
        Mongo filter for (field, operator, value) conditions. Each condition gets its own clause
        under $and, so several conditions on one field (a range, say) all apply.
        """
        clauses = [{key: {self.ops[operator.lower()]: value}} for (key, operator, value) in query or []]
        if len(clauses) > 1:
            return {"$and": clauses}
        return clauses[0] if clauses else {}

    def describe(self) -> Dict:
        """
        If not extracted already, retrieves database metadata
        :return: dictionary of tables and their attributes
        """

        def extract_dictionary_metadata(data):
            """
            Extracts the metadata of a dictionary
            :param data: a python dictionary
            :return: a dictionary containing the metadata
            """
            return {
                key: (
                    type(data[key]).__name__
                    if type(data[key]).__name__ != "dict"
                    else extract_dictionary_metadata(data[key])
                )
                for key in data.keys()
            }

        if self.metadata is None:
            tables = self.db.list_collection_names()
            metadata = {}
            for table in tables:
                record = self.db[table].find_one()
                if record is not None:
                    metadata[table] = extract_dictionary_metadata(record)
            self.metadata = metadata
        return self.metadata

    def remove_table_prefix(self, id: str) -> str:
        """
        emoves the table prefix if it exists in the id
        :param id: an id (staff/08ab25687cf or 08ab25687cf)
        :return: a non prefixed id
        """
        pattern = r'^[a-zA-Z_][a-zA-Z0-9_]*\/(.*)$'
        return re.sub(pattern, r'\1', id)

    def id(self, table: str=None) -> str:
        """
        Returns a unique id for the specific table
        :param table: name of the table
        :return: the next id to ve used according to context
        """
        # return f"{table}/{str(ObjectId())}" if table else f"{str(ObjectId())}"
        return str(ObjectId())

    def insert(self, table: str, record: Dict, get_next_id: bool=False, timestamp: bool = True, version: bool = True) -> Dict or None:
        """
        Inserts a single document in the target table/collection
        :param table: name of the table/collection
        :param record: record to insert
        :param timestamp: whether to insert timestamp or not
        :param version: whether to insert version or not
        :return: the inserted record as a dictionary
        """
        if version:
            record["_version"] = 1
        if timestamp:
            record["_created"] = record["_updated"] = datetime.now(timezone.utc)
        try:
            id = record.pop("id", None)
            _id = record.pop("_id", None)
            id = id if id else _id
            record["_id"] = id if id else str(ObjectId())
            # Insert/Replace the table prefix in ID
            # record["_id"] = f"{table}/{self.remove_table_prefix(record['_id'])}"
            record["_id"] = self.db[table].insert_one(record).inserted_id
            return record
        except pymongo.errors.DuplicateKeyError as e:
            logging.warning(msg=f"Duplicated key (table={table}, id={record['_id']})")
            return None

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
        try:
            # Handle ID
            id = record.pop("id", None)
            _id = record.pop("_id", None)
            id = id if id else _id
            record["_id"] = id if id else str(ObjectId())

            # Add meta fields
            if version:
                record["_version"] = 1
            if timestamp:
                now = datetime.now(timezone.utc)
                # If the document already exists, preserve the original _created
                existing = self.db[table].find_one({"_id": record["_id"]})
                record["_created"] = existing["_created"] if existing and "_created" in existing else now
                record["_updated"] = now

            # Upsert (replace the full document)
            self.db[table].replace_one({"_id": record["_id"]}, record, upsert=True)

            return record

        except Exception as e:
            logging.error(f"Failed to upsert document into {table}: {e}")
            return None

    def update(self, table: str, id: Any, record: Dict, timestamp: bool = True) -> Dict:
        """
        Updates a record with the newest info provided
        :param table: name of the table/collection
        :param id: unique id identifying the record to update
        :param record: dictionary with fields to update
        :param timestamp: whether to insert timestamp or not
        :return: the updated record as a Dict
        """
        try:
            # eliminate the version key to avoid conflicts while updating in database
            record.pop("_version", None)
            record.pop("_id", None)
            record.pop("id", None)
            record["_updated"] = datetime.now(timezone.utc)
            record = self.db[table].find_one_and_update(
                {"_id": id},
                {"$inc": {"_version": 1}, "$set": record},
                return_document=ReturnDocument.AFTER,
                upsert=False,
            )
        except pymongo.errors.PyMongoError as e:
            logging.error(msg=e)
        return record

    def find_by_id(self, table: str, id: Any, keys: List[str] = "*", expand: List[str or Tuple] = None, meta: Dict = None) -> Dict or None:
        """
        Locates a record within a table/collection using its unique ID
        :param table: name of the table/collection to search
        :param id: unique id identifying the record
        :param keys: list of fields to retrieve
        :param expand: list of fields to expand
        :param meta: Object metadata necessary to join reference fields
        :return: The record, if found, None otherwise
        """
        projection = None if keys == "*" else {k: 1 for k in keys}

        pipeline = [{"$match": {"_id": id}}]

        if expand:
            if meta:
                for key in expand:
                    if key not in meta.get("references", {}):
                        logging.warning(msg=f"{key} not in {meta.get('class', 'Unknown')} references")
                        continue
                    ref = meta["references"][key]

                    # Add lookup stage
                    pipeline.append({"$lookup": {
                        "from": ref["table"],
                        "localField": key,
                        "foreignField": "_id",
                        "as": key
                    }})

                    # Handle unwinding for non-array references with null preservation
                    if not ref["is_array"]:
                        pipeline.append({"$unwind": {
                            "path": f"${key}",
                            "preserveNullAndEmptyArrays": True
                        }})
            else:
                for (key, _table, is_array) in expand:
                    pipeline.append({"$lookup": {
                        "from": _table,
                        "localField": key,
                        "foreignField": "_id",
                        "as": key
                    }})
                    if not is_array:
                        pipeline.append({"$unwind": {"path": f"${key}"}})

        if projection:
            pipeline.append({"$project": projection})

        result = list(self.db[table].aggregate(pipeline))
        return result[0] if result else None

    def find_by_key_value(self, table: str, key: str, op: str="==", value: Any = None, expand: List[str] = None, keys: List[str] = "*", meta: Dict=None) -> List[Dict]:
        """
        Retrieves a set of records which match a specific condition using a ket-value pair
        :param table: name of the table/collection for search
        :param key: name of the search key
        :param op: operator to use (==, !=, >, >=, <, <=, like, in, not-in)
        :param value: value to match the key
        :param keys: list of fields to retrieve, all if not specified
        :param meta: Object metadata necessary to join reference fields
        :return: a list of matching records or empty list if not found
        """
        return self.fetch(table=table, query=[(key, op, value)], expand=expand, keys=keys, meta=meta)

    def find_by_key_value_like(self, table: str, key: str, value: Any, expand: List[str] = None, keys: List[str] = "*", meta: Dict=None) -> List[Dict]:
        """
        Retrieves a set of records which loosely match a specific condition using a ket-value pair
        :param table: name of the table/collection for search
        :param key: name of the search key
        :param value: value contained in the key (substring)
        :param keys: list of fields to retrieve, all if not specified
        :param meta: Object metadata necessary to join reference fields
        :return: a list of matching records or empty list if not found
        """
        return self.fetch(table=table, query=[(key, "like", value)], expand=expand, keys=keys, meta=meta)

    def find_objects_list(self, table: str, ids: List, expand: List[str] = None, keys: List[str] = "*", meta: Dict = None) -> List[Dict]:
        """
        Given a list of ids, retrieve corresponding records within a collection.
        Supports field selection and reference expansion.

        :param table: Name of the collection
        :param ids: List of document _id values (with or without prefix)
        :param expand: List of fields to expand via $lookup
        :param keys: List of fields to project, or '*' to return all
        :param meta: Metadata for reference expansion
        :return: List of matching documents
        """
        # Ensure all IDs are properly prefixed
        # ids = [id if table in id else f"{table}/{id}" for id in ids]

        # Build the query: _id IN ids
        query = [("_id", "in", ids)]

        # Use the generic fetch function
        return self.fetch(table=table, query=query, keys=keys, expand=expand, meta=meta)

    def fetch(self, table: str, query: List[Tuple]=None, keys: List[str] = "*", sample: int = 0, sort_by: List[Tuple[str,int]]=None, expand: List[str]=None, meta: Dict=None) -> List[Dict]:
        """
        Returns all records within a table/collection. Can be called using object's metadata to expand references
        :param table: Table name
        :param query: List of (key,value,op) tuples representing ANDed conditions (op might be ==, >, >= ...)
        :param keys: list of fields to return, if not specified, returns all fields
        :param expand: list of fields to expand from reference(s) (JOIN)
        :param meta: Object metadata necessary to join reference fields
        :return: All records from table/collection
        """
        projection = None if keys == "*" else {k: 1 for k in keys}
        query = [] if not query else query
        expand = [] if not expand else expand

        if not query:
                results = self.db[table].find({}, projection)
        pipeline = list()
        match = self._filter(query)
        pipeline.append({"$match": match})  # add the match query
        # Expand - consider that the name of the key corresponds with the id of the table (convert to plural)
        if projection:
            pipeline.append({"$project": projection})
        if expand:
            if meta:
                for key in expand:
                    if key not in meta["references"].keys():
                        logging.warning(msg=f"{key} not in {meta['class']} references")
                        continue
                    ref = meta["references"][key]
                    pipeline.append(
                        {"$lookup": {"from": ref["table"], "localField": key, "foreignField": "_id", "as": key}})
                    if not ref["is_array"]:
                        pipeline.append({"$unwind": {"path": f"${key}", "preserveNullAndEmptyArrays": True}})
            else:
                # When no meta is provided, expand keys is a list of tuples indicating [(key:str, table:str, is_array:bool)]
                for (key, _table, is_array) in expand:
                    pipeline.append(
                        {"$lookup": {"from": _table, "localField": key, "foreignField": "_id", "as": key}})
                    if not is_array:
                        pipeline.append({"$unwind": {"path": f"${key}", "preserveNullAndEmptyArrays": True}})
        if sort_by:
            pipeline.append({"$sort": {k:v for k,v in sort_by if v in [-1, 1]}})
        if sample > 0:
            pipeline.append({"$sample": {"size": sample}})
        if projection:
            pipeline.append({"$project": projection})
        results = self.db[table].aggregate(pipeline)
        yield from results

    def delete(self, table: str, id: Any, physical_delete: bool=True) -> bool:
        """
        Deletes a record from a table/collection given a valid id
        :param table: Name of the table/collection
        :param id: Valid id
        :return: True if record exists, False otherwise
        """
        # TODO: eliminate this concatenation when ids are stripped from table prefix
        # id = f"{table}/{id.split('/')[-1]}"
        if physical_delete:
            return self.db[table].delete_one({"_id": id}).deleted_count > 0
        result = self.db[table].update_one({"_id": id}, {"$set": {"_state": "DELETED"}})
        return result.modified_count > 0

    def delete_objects_list(self, table: str, ids: List, physical_delete: bool=True) -> int:
        """
        Given a list of ids, delete corresponding records within table/collection
        :param table: name of the table/collection
        :param ids: list of ids
        :param physical_delete: whether to delete physical records or just mark them as deleted
        :return: Number of deleted records
        """
        # TODO: eliminte when table prefix is eliminated from ids in Spore
        # ids = [id if table in id else f"{table}/{id}" for id in ids]
        if physical_delete:
            return self.db[table].delete_many({"_id": {"$in": ids}}).deleted_count
        return self.db[table].update_many({"_id": {"$in": ids}}, {"$set": {"_state": "DELETED"}}).modified_count

    def delete_many(self, table: str, query: List[Tuple]=None, physical_delete: bool=False) -> int:
        query = [] if not query else query
        match = self._filter(query)
        if physical_delete:
            return self.db[table].delete_many(match).deleted_count > 0
        result = self.db[table].update_many(match, {"$set": {"_state": "DELETED"}})
        return result.modified_count > 0

    def delete_all(self, table: str, physical_delete: bool=False) -> int:
        """
        Delete all records from a table/collection
        :param table: name of the table/collection
        :param physical_delete: whether to delete physical records or just mark them as deleted
        :return: Number of deleted records
        """
        if physical_delete:
            return self.db[table].delete_many({}).deleted_count
        result = self.db[table].update_many({}, {"$set": {"_state": "DELETED"}})
        return result.modified_count > 0

    def distinct(self, table: str, key: str, query: List[Tuple] = []) -> List[Any]:
        """
        Retrieves the set of unique values from a field within a table
        :param table: name of table/collection
        :param key: name of field within table (column)
        :param query: List of tuples containing AND conditions; [('name', 'Josh'), ('lastname','Linforth')]
        :return: List of unique values of key within collection
        """
        query = {k: v for (k, v) in query}
        return self.db[table].distinct(key=key, filter=query)

    def execute_raw_query(self, table: str, query: Tuple[str, Dict or List]) -> Any:
        """
        Allows execution of a low level query using pymongo syntax
        :param table: name of the table/collection
        :param query: a structure describing the query to execute
        :return: The type depends on the query
        """
        operation = query[0]
        pipeline = query[1]
        if operation == "aggregate":
            return self.db[table].aggregate(pipeline)
        if operation == "delete":
            return self.db[table].delete_many(pipeline)
        if operation == "find":
            return self.db[table].find(pipeline)

    def drop(self, table: str):
        """
        Delete table/collection
        :param table: name of the table/collection
        :return: True if table was deleted, False otherwise
        """
        self.db[table].drop()


if __name__ == '__main__':
    import json

    dao = MongoDAO(dbname="padmi")

    # TESTs expandable fields passing tuples
    print(dao.find_by_id(table="matches", id="009_001_2025041020002130", expand=[("club", "clubs", False),("court","courts", False)]))

    # Test logical/physical deletion of a query result
    # print(dao.delete_many(table="matches", query=[("club","==","clubs/007"),("date","==","2025-04-10")], physical_delete=False))
    # matches = dao.fetch(table="matches", query=[("club","==","clubs/007"),("date","==","2025-04-10")])
    # print(*matches, sep="\n")
    # print(dao.delete_many(table="matches", ids=ids, physical_delete=True))
    # matches = dao.find_objects_list(table="matches", ids=ids)
    # print(*matches)


    # Test logical/physical deletion of a list of documents
    # ids = ["006_001_2025041009301100", "006_001_2025041011001230"]
    # print(dao.delete_objects_list(table="matches", ids=ids, physical_delete=False))
    # matches = dao.find_objects_list(table="matches", ids=ids)
    # print(*matches, sep="\n")
    # print(dao.delete_objects_list(table="matches", ids=ids, physical_delete=True))
    # matches = dao.find_objects_list(table="matches", ids=ids)
    # print(*matches)


    # Test logical/physical deletion of one document
    # dao.delete(table="matches", id="001_008_2024030415151645", physical_delete=False)
    # match = dao.find_by_id(table="matches", id="001_008_2024030415151645")
    # print(match)
    # dao.delete(table="matches", id="001_008_2024030415151645", physical_delete=True)
    # match = dao.find_by_id(table="matches", id="001_008_2024030415151645")
    # print(match)

    # TEST expand fields (join) with no meta data, passing tuples (key, table, is_array)
    # clubs = dao.fetch(table="clubs", query=[("_id", "in", ["clubs/009", "clubs/004"])], expand=[("courts", "courts", True)])
    # for club in clubs:
    #     print(json.dumps(club, indent=4, default=str))

    # TEST fetch with $in, $all and $eq
    # print(json.dumps(dao.describe(), indent=4))
    # admins = dao.fetch(table="profiles", query=[("roles", "all-in", ["admin", "user"])], keys=["name", "email", "roles"])
    # admins = dao.fetch(table="profiles", query=[("roles", "in", ["admin"])], keys=["name", "email", "roles"], sort_by=[("email",1)])
    # admins = dao.fetch(table="profiles", query=[("roles", "==", "admin")], keys=["name", "email", "roles"])
    # print(*admins, sep="\n")

    # dao = MongoDAO(dbname="padmi")
    #
    # pipeline = [
    #     {"$match": {"state": "VALID"}},
    #     {"$unwind": "$data.hits"},
    #     {
    #         "$group": {
    #             "_id": "$data.hits.name",
    #             "totalSpeed": {
    #                 "$sum": {
    #                     "$multiply": [
    #                         "$data.hits.speed_avg",
    #                         {"$add": ["$data.hits.good", "$data.hits.bad"]}
    #                     ]
    #                 }
    #             },
    #             "totalHits": {
    #                 "$sum": {"$add": ["$data.hits.good", "$data.hits.bad"]}
    #             },
    #             "totalGood": {"$sum": "$data.hits.good"},
    #             "totalBad": {"$sum": "$data.hits.bad"},
    #             "totalWinners": {"$sum": "$data.hits.winners"},
    #             "count": {"$sum": 1}
    #         }
    #     },
    #     {
    #         "$project": {
    #             "name": "$_id",
    #             "speed_avg": {
    #                 "$cond": [
    #                     {"$eq": ["$totalHits", 0]},
    #                     0,
    #                     {"$divide": ["$totalSpeed", "$totalHits"]}
    #                 ]
    #             },
    #             "avg_in": {"$divide": ["$totalGood", "$count"]},
    #             "avg_out": {"$divide": ["$totalBad", "$count"]},
    #             "avg_winners": {"$divide": ["$totalWinners", "$count"]},
    #             "_id": 0
    #         }
    #     }
    # ]
    #
    # response = dao.execute_raw_query(table="matches_data", query=("aggregate", pipeline))
    # print(*response, sep="\n")

    # matches = dao.find_objects_list(table="matches", ids=['matches/018_001_2025031910301200', 'matches/018_001_2025032014581530', 'matches/018_001_2025032215001630'])
    # print(*matches, sep="\n")

    # dao = MongoDAO(dbname="pademy")
    # lessons = dao.fetch(table="lessons", sample=3, query=[("club", "like", "004")], sort_by=[("club",1),("when",-1)])
    # print(*lessons, sep="\n")
    # record = dao.find_by_id(table="lessons", id="lessons/100_004_2024101810001100", expand=["club", "trainer", "players"])
    # record = dao.find_by_id(table="lessons", id="lessons/100_004_2024101810001100")
    # record = dao.find_by_id(table="lessons", id="100_004_2024101810001100")
    # print(json.dumps(record, indent=4, default=str))
'''    staff = [
        {"project_id": "PADMI", "name": "Vanesa Lomas", "email": "vanesa@padmi.es", "actual_role": {"role": "Data Engineer", "level": "Mid-Level"}, "team": "Computer Vision", "phases": None, "softskills": {"belbin": {"spi": {"primary": {"CF": 0.97, "ME": 0.829}, "secondary": {"PL": 0.628, "SH": 0.42, "SP": 0.408, "IMP": 0.399, "TW": 0.37, "RI": 0.25}, "avoid": {"CO": 0.001}}}}, "hardskills": None, "pdp": None, "_version": 1, "_created": "2024-08-19 15:03:55.592000", "_updated": "2024-08-19 15:03:55.592000"},
        {"project_id": "PADMI", "name": "Jos\u00e9 N\u00e1jera", "email": "jose@padmi.es", "actual_role": {"role": "CTO", "level": "Manager"}, "team": "Management", "phases": None, "softskills": {"belbin": {"spi": {"primary": {"PL": 0.941, "CO": 0.749, "RI": 0.728}, "secondary": {"SP": 0.62, "TW": 0.37, "SH": 0.349}, "avoid": {"ME": 0.208, "IMP": 0.199, "CF": 0.17}}}}, "hardskills": None, "pdp": None, "_version": 1, "_created": "2024-08-19 15:03:55.592000", "_updated": "2024-08-19 15:03:55.592000"},
        {"project_id": "PADMI", "name": "Javier Mart\u00ednez", "email": "javi@padmi.es", "actual_role": {"role": "Data Engineer", "level": "Mid-Level"}, "team": "Computer Vision", "phases": None, "softskills": {"belbin": {"spi": {"primary": {"PL": 0.979, "CF": 0.82, "RI": 0.658}, "secondary": {"TW": 0.578, "SP": 0.479, "IMP": 0.399}, "avoid": {"ME": 0.129, "SH": 0.001, "CO": 0.001}}}}, "hardskills": None, "pdp": None, "_version": 1, "_created": "2024-08-19 15:03:55.595000", "_updated": "2024-08-19 15:03:55.595000"},
        {"project_id": "PADMI", "name": "Eugenio Saiz Montes", "email": "uge@padmi.es", "actual_role": {"role": "CEO", "level": "Senior"}, "team": "Management", "phases": None, "softskills": None, "hardskills": None, "pdp": None, "_version": 1, "_created": "2024-08-19 15:03:55.596000", "_updated": "2024-08-19 15:03:55.596000"},
        {"project_id": "PADMI", "name": "Guille Blanco", "email": "guille@padmi.es", "actual_role": {"role": "Backend Developer", "level": "Mid-Level"}, "team": "Backend", "phases": None, "softskills": {"belbin": {"spi": {"primary": {"CF": 0.749, "TW": 0.749, "PL": 0.741}, "secondary": {"RI": 0.599, "ME": 0.599, "CO": 0.457, "IMP": 0.258}, "avoid": {"SH": 0.157, "SP": 0.149}}}}, "hardskills": None, "pdp": None, "_version": 1, "_created": "2024-08-19 15:03:55.597000", "_updated": "2024-08-19 15:03:55.597000"},
        {"project_id": "PADMI", "name": "Yoana Ugarte", "email": "yoana@padmi.es", "actual_role": {"role": "iOS Developer", "level": "Senior"}, "team": "Apps", "phases": None, "softskills": {"belbin": {"spi": {"primary": {"PL": 0.891, "SP": 0.829}, "secondary": {"TW": 0.641, "ME": 0.599, "CO": 0.457, "SH": 0.42, "RI": 0.328}, "avoid": {"CF": 0.241, "IMP": 0.199}}}}, "hardskills": None, "pdp": None, "_version": 1, "_created": "2024-08-19 15:03:55.598000", "_updated": "2024-08-19 15:03:55.598000"},
        {"project_id": "PADMI", "name": "Francho Mel\u00e9ndez", "email": "francho@padmi.es", "actual_role": {"role": "Data Scientist", "level": "Senior"}, "team": "Computer Vision", "phases": None, "softskills": {"belbin": {"spi": {"primary": {"PL": 0.991, "RI": 0.92, "SP": 0.791}, "secondary": {"ME": 0.599, "TW": 0.508, "CF": 0.349}, "avoid": {"CO": 0.108, "SH": 0.079, "IMP": 0.07}}}}, "hardskills": None, "pdp": None, "_version": 1, "_created": "2024-08-19 15:03:55.599000", "_updated": "2024-08-19 15:03:55.599000"},
        {"project_id": "PADMI", "name": "Mel de Melo", "email": "mel@padmi.es", "actual_role": {"role": "Android Developer", "level": "Junior"}, "team": "Apps", "phases": None, "softskills": {"belbin": {"spi": {"primary": {"TW": 0.749, "CF": 0.708, "RI": 0.658}, "secondary": {"PL": 0.57, "IMP": 0.541, "SH": 0.42, "SP": 0.408, "CO": 0.399, "ME": 0.279}, "avoid": {}}}}, "hardskills": None, "pdp": None, "_version": 1, "_created": "2024-08-19 15:03:55.600000", "_updated": "2024-08-19 15:03:55.600000"},
        {"project_id": "PADMI", "name": "Hugo Polo", "email": "hugo@padmi.es", "actual_role": {"role": "Android Developer", "level": "Senior"}, "team": "Apps", "phases": None, "softskills": {"belbin": {"spi": {"primary": {"PL": 0.778, "CO": 0.749}, "secondary": {"IMP": 0.607, "ME": 0.599, "SP": 0.55, "CF": 0.529, "RI": 0.508, "TW": 0.291}, "avoid": {"SH": 0.208}}}}, "hardskills": None, "pdp": None, "_version": 1, "_created": "2024-08-19 15:03:55.601000", "_updated": "2024-08-19 15:03:55.601000"},
        {"project_id": "662520e97836b3fb9c101525", "name": "Alison Turner", "email": "alison.turner@acme.com", "actual_role": {"role": "Frontend Engineer", "level": "Tech Lead"}, "team": "FACTORY", "phases": {"start": {"bootcamp_seminar": True}, "workstyle": {"soft_skills_workshop": True, "spi": True, "observers": True}, "skills": {"hard_skills_workshop": True, "actual_role": True, "target_role": True, "skills_gap_analysis": True, "pdp": True}}, "softskills": {"belbin": {"spi": {"primary": {"RI": 0.728, "ME": 0.728}, "secondary": {"CO": 0.641, "TW": 0.641, "PL": 0.628, "CF": 0.47, "SP": 0.341}, "avoid": {"IMP": 0.199, "SH": 0.157}}}}, "hardskills": {"actual_role": {"role": "Frontend Engineer", "level": "Tech Lead"}, "target_role": {"role": "Fullstack Engineer", "level": "Tech Lead"}, "skills_gaps": []}, "pdp": None, "_version": 1, "_created": "2024-08-19 15:05:28.590000", "_updated": "2024-08-19 15:05:28.590000"},
        {"project_id": "662520e97836b3fb9c101525", "name": "Adam Mitchell", "email": "adam.mitchell@acme.com", "actual_role": {"role": "Backend Engineer", "level": "Junior"}, "team": "FACTORY", "phases": {"start": {"bootcamp_seminar": True}, "workstyle": {"soft_skills_workshop": True, "spi": True, "observers": True}, "skills": {"hard_skills_workshop": True, "actual_role": True, "target_role": True, "skills_gap_analysis": True, "pdp": True}}, "softskills": {"belbin": {"spi": {"primary": {"IMP": 0.82, "PL": 0.808, "SH": 0.808}, "secondary": {"RI": 0.599, "SP": 0.479, "CF": 0.291, "ME": 0.279}, "avoid": {"TW": 0.22, "CO": 0.208}}}}, "hardskills": {"actual_role": {"role": "Backend Engineer", "level": "Junior"}, "target_role": {"role": "Backend Engineer", "level": "Mid_Level"}, "skills_gaps": []}, "pdp": None, "_version": 1, "_created": "2024-08-19 15:05:28.591000", "_updated": "2024-08-19 15:05:28.591000"},
        {"project_id": "662520e97836b3fb9c101525", "name": "Eve Summers", "email": "eve.summers@acme.com", "actual_role": {"role": "Backend Engineer", "level": "Junior"}, "team": "DATA", "phases": {"start": {"bootcamp_seminar": True}, "workstyle": {"soft_skills_workshop": True, "spi": True, "observers": True}, "skills": {"hard_skills_workshop": True, "actual_role": True, "target_role": True, "skills_gap_analysis": True, "pdp": True}}, "softskills": {"belbin": {"spi": {"primary": {"RI": 0.92, "SP": 0.899, "PL": 0.849}, "secondary": {"SH": 0.491, "ME": 0.441, "TW": 0.291, "CO": 0.27}, "avoid": {"CF": 0.141, "IMP": 0.091}}}}, "hardskills": {"actual_role": {"role": "Backend Engineer", "level": "Junior"}, "target_role": {"role": "Backend Engineer", "level": "Mid_Level"}, "skills_gaps": []}, "pdp": None, "_version": 1, "_created": "2024-08-19 15:05:28.591000", "_updated": "2024-08-19 15:05:28.591000"},
        {"project_id": "662520e97836b3fb9c101525", "name": "Anna Nichols", "email": "anna.nichols@acme.com", "actual_role": {"role": "Backend Engineer", "level": "Junior"}, "team": "FACTORY", "phases": {"start": {"bootcamp_seminar": True}, "workstyle": {"soft_skills_workshop": True, "spi": True, "observers": True}, "skills": {"hard_skills_workshop": True, "actual_role": True, "target_role": True, "skills_gap_analysis": True, "pdp": True}}, "softskills": {"belbin": {"spi": {"primary": {"CO": 0.92, "SH": 0.899, "PL": 0.741, "RI": 0.658}, "secondary": {"IMP": 0.607, "ME": 0.441}, "avoid": {"SP": 0.208, "TW": 0.108, "CF": 0.001}}}}, "hardskills": {"actual_role": {"role": "Backend Engineer", "level": "Junior"}, "target_role": {"role": "Backend Engineer", "level": "Mid_Level"}, "skills_gaps": []}, "pdp": None, "_version": 1, "_created": "2024-08-19 15:05:28.592000", "_updated": "2024-08-19 15:05:28.592000"},
        {"project_id": "662520e97836b3fb9c101525", "name": "Carlos Ruiz", "email": "carlos.ruiz@acme.com", "actual_role": {"role": "Software Engineer", "level": "Senior"}, "team": "FACTORY", "phases": {"start": {"bootcamp_seminar": True}, "workstyle": {"soft_skills_workshop": True, "spi": True, "observers": True}, "skills": {"hard_skills_workshop": True, "actual_role": True, "target_role": True, "skills_gap_analysis": True, "pdp": True}}, "softskills": {"belbin": {"spi": {"primary": {"CF": 0.87, "PL": 0.808, "ME": 0.728}, "secondary": {"SP": 0.62, "RI": 0.508, "CO": 0.399, "TW": 0.291, "IMP": 0.258}, "avoid": {"SH": 0.208}}}}, "hardskills": {"actual_role": {"role": "Software Engineer", "level": "Senior"}, "target_role": {"role": "Senior Software Engineer", "level": ""}, "skills_gaps": []}, "pdp": None, "_version": 1, "_created": "2024-08-19 15:05:28.593000", "_updated": "2024-08-19 15:05:28.593000"},
        {"project_id": "662520e97836b3fb9c101525", "name": "Duncan Myers", "email": "duncan.myers@acme.com", "actual_role": {"role": "Software Engineer", "level": "Senior"}, "team": "PLATFORM", "phases": {"start": {"bootcamp_seminar": True}, "workstyle": {"soft_skills_workshop": True, "spi": True, "observers": True}, "skills": {"hard_skills_workshop": True, "actual_role": True, "target_role": True, "skills_gap_analysis": True, "pdp": True}}, "softskills": {"belbin": {"spi": {"primary": {"SH": 0.949, "PL": 0.891, "RI": 0.891}, "secondary": {"CF": 0.62, "ME": 0.441, "CO": 0.399}, "avoid": {"TW": 0.157, "IMP": 0.091, "SP": 0.057}}}}, "hardskills": {"actual_role": {"role": "Software Engineer", "level": "Senior"}, "target_role": {"role": "Software Engineer", "level": "Lead"}, "skills_gaps": []}, "pdp": None, "_version": 1, "_created": "2024-08-19 15:05:28.594000", "_updated": "2024-08-19 15:05:28.594000"},
        {"project_id": "662520e97836b3fb9c101525", "name": "Felix Stewart", "email": "felix.stewart@acme.com", "actual_role": {"role": "Backend Engineer", "level": "Senior"}, "team": "PLATFORM", "phases": {"start": {"bootcamp_seminar": True}, "workstyle": {"soft_skills_workshop": True, "spi": True, "observers": True}, "skills": {"hard_skills_workshop": True, "actual_role": True, "target_role": True, "skills_gap_analysis": True, "pdp": True}}, "softskills": {"belbin": {"spi": {"primary": {"TW": 0.891, "IMP": 0.778, "PL": 0.741, "SP": 0.679}, "secondary": {"RI": 0.599, "ME": 0.358, "SH": 0.279}, "avoid": {"CF": 0.17, "CO": 0.108}}}}, "hardskills": {"actual_role": {"role": "Backend Engineer", "level": "Senior"}, "target_role": {"role": "Fullstack Engineer", "level": "Mid_Level"}, "skills_gaps": []}, "pdp": None, "_version": 1, "_created": "2024-08-19 15:05:28.594000", "_updated": "2024-08-19 15:05:28.594000"},
        {"project_id": "662520e97836b3fb9c101525", "name": "Danny Price", "email": "danny.price@acme.com", "actual_role": {"role": "Backend Engineer", "level": "Junior"}, "team": "FACTORY", "phases": {"start": {"bootcamp_seminar": True}, "workstyle": {"soft_skills_workshop": True, "spi": True, "observers": True}, "skills": {"hard_skills_workshop": True, "actual_role": True, "target_role": True, "skills_gap_analysis": True, "pdp": True}}, "softskills": {"belbin": {"spi": {"primary": {"SP": 0.991, "IMP": 0.849, "SH": 0.77, "TW": 0.749}, "secondary": {}, "avoid": {"ME": 0.208, "CF": 0.17, "RI": 0.157, "PL": 0.001, "CO": 0.001}}}}, "hardskills": {"actual_role": {"role": "Backend Engineer", "level": "Junior"}, "target_role": {"role": "Backend Engineer", "level": "Mid_Level"}, "skills_gaps": []}, "pdp": None, "_version": 1, "_created": "2024-08-19 15:05:28.595000", "_updated": "2024-08-19 15:05:28.595000"},
        {"project_id": "662520e97836b3fb9c101525", "name": "Dylan Harper", "email": "dylan.harper@acme.com", "actual_role": {"role": "Data Scientist", "level": "Mid_Level"}, "team": "DATA", "phases": {"start": {"bootcamp_seminar": True}, "workstyle": {"soft_skills_workshop": True, "spi": True, "observers": True}, "skills": {"hard_skills_workshop": True, "actual_role": True, "target_role": True, "skills_gap_analysis": True, "pdp": True}}, "softskills": {"belbin": {"spi": {"primary": {"PL": 0.92, "ME": 0.67}, "secondary": {"SP": 0.62, "RI": 0.599, "TW": 0.578, "SH": 0.491, "CF": 0.47, "IMP": 0.399}, "avoid": {"CO": 0.001}}}}, "hardskills": {"actual_role": {"role": "Data Scientist", "level": "Mid_Level"}, "target_role": {"role": "Data Scientist", "level": "Senior"}, "skills_gaps": []}, "pdp": None, "_version": 1, "_created": "2024-08-19 15:05:28.596000", "_updated": "2024-08-19 15:05:28.596000"},
        {"project_id": "662520e97836b3fb9c101525", "name": "Isabelle Gardner", "email": "isabelle.gardner@acme.com", "actual_role": {"role": "Backend Engineer", "level": "Mid_Level"}, "team": "FACTORY", "phases": {"start": {"bootcamp_seminar": True}, "workstyle": {"soft_skills_workshop": True, "spi": True, "observers": True}, "skills": {"hard_skills_workshop": True, "actual_role": True, "target_role": True, "skills_gap_analysis": True, "pdp": True}}, "softskills": {"belbin": {"spi": {"primary": {"PL": 0.958, "SP": 0.949, "RI": 0.728, "ME": 0.728}, "secondary": {"IMP": 0.47, "CO": 0.27}, "avoid": {"TW": 0.22, "CF": 0.001, "SH": 0.001}}}}, "hardskills": {"actual_role": {"role": "Backend Engineer", "level": "Mid_Level"}, "target_role": {"role": "Backend Engineer", "level": "Senior"}, "skills_gaps": []}, "pdp": None, "_version": 1, "_created": "2024-08-19 15:05:28.597000", "_updated": "2024-08-19 15:05:28.597000"},
        {"project_id": "662520e97836b3fb9c101525", "name": "Jack Douglas", "email": "jack.douglas@acme.com", "actual_role": {"role": "Backend Engineer", "level": "Mid_Level"}, "team": "PLATFORM", "phases": {"start": {"bootcamp_seminar": True}, "workstyle": {"soft_skills_workshop": True, "spi": True, "observers": True}, "skills": {"hard_skills_workshop": True, "actual_role": True, "target_role": True, "skills_gap_analysis": True, "pdp": True}}, "softskills": {"belbin": {"spi": {"primary": {"TW": 0.941, "PL": 0.778, "CO": 0.699}, "secondary": {"SH": 0.62, "RI": 0.328, "ME": 0.279, "SP": 0.27}, "avoid": {"CF": 0.17, "IMP": 0.001}}}}, "hardskills": {"actual_role": {"role": "Backend Engineer", "level": "Mid_Level"}, "target_role": {"role": "Backend Engineer", "level": "Senior"}, "skills_gaps": []}, "pdp": None, "_version": 1, "_created": "2024-08-19 15:05:28.597000", "_updated": "2024-08-19 15:05:28.597000"},
        {"project_id": "662520e97836b3fb9c101525", "name": "Luke Kennedy", "email": "luke.kennedy@acme.com", "actual_role": {"role": "Backend Engineer", "level": "Mid_Level"}, "team": "PLATFORM", "phases": {"start": {"bootcamp_seminar": True}, "workstyle": {"soft_skills_workshop": True, "spi": True, "observers": True}, "skills": {"hard_skills_workshop": True, "actual_role": True, "target_role": True, "skills_gap_analysis": True, "pdp": True}}, "softskills": {"belbin": {"spi": {"primary": {"PL": 0.958, "RI": 0.949, "TW": 0.691}, "secondary": {"SP": 0.55, "CO": 0.328, "SH": 0.279, "ME": 0.279}, "avoid": {"IMP": 0.091, "CF": 0.001}}}}, "hardskills": {"actual_role": {"role": "Backend Engineer", "level": "Mid_Level"}, "target_role": {"role": "Backend Engineer", "level": "Senior"}, "skills_gaps": []}, "pdp": None, "_version": 1, "_created": "2024-08-19 15:05:28.598000", "_updated": "2024-08-19 15:05:28.598000"},
        {"project_id": "662520e97836b3fb9c101525", "name": "Jameson Sinclair", "email": "jameson.sinclair@acme.com", "actual_role": {"role": "Backend Engineer", "level": "Mid_Level"}, "team": "FACTORY", "phases": {"start": {"bootcamp_seminar": True}, "workstyle": {"soft_skills_workshop": True, "spi": True, "observers": True}, "skills": {"hard_skills_workshop": True, "actual_role": True, "target_role": True, "skills_gap_analysis": True, "pdp": True}}, "softskills": {"belbin": {"spi": {"primary": {"CO": 0.829}, "secondary": {"IMP": 0.607, "CF": 0.578, "TW": 0.578, "SP": 0.479, "RI": 0.42, "PL": 0.408, "ME": 0.358, "SH": 0.349}, "avoid": {}}}}, "hardskills": {"actual_role": {"role": "Backend Engineer", "level": "Mid_Level"}, "target_role": {"role": "Backend Engineer", "level": "Senior"}, "skills_gaps": []}, "pdp": None, "_version": 1, "_created": "2024-08-19 15:05:28.598000", "_updated": "2024-08-19 15:05:28.598000"},
        {"project_id": "662520e97836b3fb9c101525", "name": "Jacob Butler", "email": "jacob.butler@acme.com", "actual_role": {"role": "Backend Engineer", "level": "Junior"}, "team": "FACTORY", "phases": {"start": {"bootcamp_seminar": True}, "workstyle": {"soft_skills_workshop": True, "spi": True, "observers": True}, "skills": {"hard_skills_workshop": True, "actual_role": True, "target_role": True, "skills_gap_analysis": True, "pdp": True}}, "softskills": {"belbin": {"spi": {"primary": {"CO": 0.941, "ME": 0.791, "TW": 0.691, "SH": 0.679}, "secondary": {"IMP": 0.607, "RI": 0.42, "SP": 0.341}, "avoid": {"CF": 0.241, "PL": 0.001}}}}, "hardskills": {"actual_role": {"role": "Backend Engineer", "level": "Junior"}, "target_role": {"role": "Backend Engineer", "level": "Mid_Level"}, "skills_gaps": []}, "pdp": None, "_version": 1, "_created": "2024-08-19 15:05:28.599000", "_updated": "2024-08-19 15:05:28.599000"},
        {"project_id": "662520e97836b3fb9c101525", "name": "Joseph Maxwell", "email": "joseph.maxwell@acme.com", "actual_role": {"role": "Backend Engineer", "level": "Senior"}, "team": "PLATFORM", "phases": {"start": {"bootcamp_seminar": True}, "workstyle": {"soft_skills_workshop": True, "spi": True, "observers": True}, "skills": {"hard_skills_workshop": True, "actual_role": True, "target_role": True, "skills_gap_analysis": True, "pdp": True}}, "softskills": {"belbin": {"spi": {"primary": {"CO": 0.991, "RI": 0.928, "PL": 0.849}, "secondary": {"ME": 0.529, "CF": 0.291}, "avoid": {"TW": 0.22, "SP": 0.208, "SH": 0.1, "IMP": 0.001}}}}, "hardskills": {"actual_role": {"role": "Backend Engineer", "level": "Senior"}, "target_role": {"role": "Fullstack Engineer", "level": "Senior"}, "skills_gaps": []}, "pdp": None, "_version": 1, "_created": "2024-08-19 15:05:28.600000", "_updated": "2024-08-19 15:05:28.600000"},
        {"project_id": "662520e97836b3fb9c101525", "name": "Marco Gomez", "email": "marco.gomez@acme.com", "actual_role": {"role": "DevOps Engineer", "level": "Senior"}, "team": "DEVOPS", "phases": {"start": {"bootcamp_seminar": True}, "workstyle": {"soft_skills_workshop": True, "spi": True, "observers": True}, "skills": {"hard_skills_workshop": True, "actual_role": True, "target_role": True, "skills_gap_analysis": True, "pdp": True}}, "softskills": {"belbin": {"spi": {"primary": {"SP": 0.991, "IMP": 0.928, "CF": 0.749, "RI": 0.728}, "secondary": {"PL": 0.408, "ME": 0.358, "SH": 0.279}, "avoid": {"TW": 0.057, "CO": 0.001}}}}, "hardskills": {"actual_role": {"role": "DevOps Engineer", "level": "Senior"}, "target_role": {"role": "DevOps Engineer", "level": "Lead"}, "skills_gaps": []}, "pdp": None, "_version": 1, "_created": "2024-08-19 15:05:28.601000", "_updated": "2024-08-19 15:05:28.601000"},
        {"project_id": "662520e97836b3fb9c101525", "name": "Jamie Roberts", "email": "jamie.roberts@acme.com", "actual_role": {"role": "Product Manager", "level": "Senior"}, "team": "PLATFORM", "phases": {"start": {"bootcamp_seminar": True}, "workstyle": {"soft_skills_workshop": True, "spi": True, "observers": True}, "skills": {"hard_skills_workshop": True, "actual_role": True, "target_role": True, "skills_gap_analysis": True, "pdp": True}}, "softskills": {"belbin": {"spi": {"primary": {"PL": 0.849, "CF": 0.82, "ME": 0.67, "RI": 0.658}, "secondary": {"SP": 0.55, "IMP": 0.328, "SH": 0.279}, "avoid": {"TW": 0.22, "CO": 0.108}}}}, "hardskills": {"actual_role": {"role": "Product Manager", "level": "Senior"}, "target_role": {"role": "Product Manager", "level": "Lead"}, "skills_gaps": []}, "pdp": None, "_version": 1, "_created": "2024-08-19 15:05:28.601000", "_updated": "2024-08-19 15:05:28.601000"},
        {"project_id": "662520e97836b3fb9c101525", "name": "Jose Newman", "email": "jose.newman@acme.com", "actual_role": {"role": "Head Software Engineering", "level": "Lead"}, "team": "LEADERSHIP", "phases": {"start": {"bootcamp_seminar": True}, "workstyle": {"soft_skills_workshop": True, "spi": True, "observers": True}, "skills": {"hard_skills_workshop": True, "actual_role": True, "target_role": True, "skills_gap_analysis": True, "pdp": True}}, "softskills": {"belbin": {"spi": {"primary": {"PL": 0.958, "SP": 0.949}, "secondary": {"RI": 0.508, "CF": 0.47, "SH": 0.42, "ME": 0.279, "IMP": 0.258}, "avoid": {"CO": 0.079, "TW": 0.049}}}}, "hardskills": {"actual_role": {"role": "Head Software Engineering", "level": "Lead"}, "target_role": {"role": "CTO", "level": "Senior"}, "skills_gaps": []}, "pdp": None, "_version": 1, "_created": "2024-08-19 15:05:28.602000", "_updated": "2024-08-19 15:05:28.602000"},
        {"project_id": "662520e97836b3fb9c101525", "name": "Grace Long", "email": "grace.long@acme.com", "actual_role": {"role": "Software Engineer", "level": "Lead"}, "team": "PLATFORM", "phases": {"start": {"bootcamp_seminar": True}, "workstyle": {"soft_skills_workshop": True, "spi": True, "observers": True}, "skills": {"hard_skills_workshop": True, "actual_role": True, "target_role": True, "skills_gap_analysis": True, "pdp": True}}, "softskills": {"belbin": {"spi": {"primary": {"PL": 0.92, "RI": 0.778}, "secondary": {"SP": 0.62, "ME": 0.599, "CF": 0.47, "TW": 0.37, "SH": 0.349}, "avoid": {"CO": 0.208, "IMP": 0.199}}}}, "hardskills": {"actual_role": {"role": "Software Engineer", "level": "Lead"}, "target_role": {"role": "Software Architect", "level": "Junior"}, "skills_gaps": []}, "pdp": None, "_version": 1, "_created": "2024-08-19 15:05:28.603000", "_updated": "2024-08-19 15:05:28.603000"},
        {"project_id": "662520e97836b3fb9c101525", "name": "Samuel Ashton", "email": "samuel.ashton@acme.com", "actual_role": {"role": "Research Engineer", "level": "Lead"}, "team": "DATA", "phases": {"start": {"bootcamp_seminar": True}, "workstyle": {"soft_skills_workshop": True, "spi": True, "observers": True}, "skills": {"hard_skills_workshop": True, "actual_role": True, "target_role": True, "skills_gap_analysis": True, "pdp": True}}, "softskills": {"belbin": {"spi": {"primary": {"PL": 0.778, "SH": 0.62}, "secondary": {"RI": 0.599, "CF": 0.578, "CO": 0.578, "ME": 0.529, "TW": 0.441, "IMP": 0.328}, "avoid": {"SP": 0.208}}}}, "hardskills": {"actual_role": {"role": "Research Engineer", "level": "Lead"}, "target_role": {"role": "Research Engineer", "level": "Principal"}, "skills_gaps": []}, "pdp": None, "_version": 1, "_created": "2024-08-19 15:05:28.603000", "_updated": "2024-08-19 15:05:28.603000"},
        {"project_id": "662520e97836b3fb9c101525", "name": "Raymond Archer", "email": "raymond.archer@acme.com", "actual_role": {"role": "Devops Engineer", "level": "Senior"}, "team": "DEVOPS", "phases": {"start": {"bootcamp_seminar": True}, "workstyle": {"soft_skills_workshop": True, "spi": True, "observers": True}, "skills": {"hard_skills_workshop": True, "actual_role": True, "target_role": True, "skills_gap_analysis": True, "pdp": True}}, "softskills": {"belbin": {"spi": {"primary": {"CF": 0.82, "ME": 0.791}, "secondary": {"SH": 0.62, "IMP": 0.607, "CO": 0.578, "PL": 0.408, "TW": 0.37, "RI": 0.328}, "avoid": {"SP": 0.108}}}}, "hardskills": {"actual_role": {"role": "Devops Engineer", "level": "Senior"}, "target_role": {"role": "Devops Engineer", "level": "Lead"}, "skills_gaps": []}, "pdp": None, "_version": 1, "_created": "2024-08-19 15:05:28.604000", "_updated": "2024-08-19 15:05:28.604000"},
        {"project_id": "662520e97836b3fb9c101525", "name": "Mohamed Zane", "email": "mohamed.zane@acme.com", "actual_role": {"role": "Machine Learning Engineer", "level": "Senior"}, "team": "DATA", "phases": {"start": {"bootcamp_seminar": True}, "workstyle": {"soft_skills_workshop": True, "spi": True, "observers": True}, "skills": {"hard_skills_workshop": True, "actual_role": True, "target_role": True, "skills_gap_analysis": True, "pdp": True}}, "softskills": {"belbin": {"spi": {"primary": {"PL": 0.999, "SP": 0.92, "TW": 0.691}, "secondary": {"RI": 0.599, "ME": 0.441, "CO": 0.399}, "avoid": {"IMP": 0.091, "CF": 0.001, "SH": 0.001}}}}, "hardskills": {"actual_role": {"role": "Machine Learning Engineer", "level": "Senior"}, "target_role": {"role": "Senior Machine Learning Engineer", "level": "Lead"}, "skills_gaps": []}, "pdp": None, "_version": 1, "_created": "2024-08-19 15:05:28.605000", "_updated": "2024-08-19 15:05:28.605000"},
        {"project_id": "662520e97836b3fb9c101525", "name": "Sarah Norton", "email": "sarah.norton@acme.com", "actual_role": {"role": "Fullstack Engineer", "level": "Senior"}, "team": "DATA", "phases": {"start": {"bootcamp_seminar": True}, "workstyle": {"soft_skills_workshop": True, "spi": True, "observers": True}, "skills": {"hard_skills_workshop": True, "actual_role": True, "target_role": True, "skills_gap_analysis": True, "pdp": True}}, "softskills": {"belbin": {"spi": {"primary": {"RI": 0.891, "SP": 0.87, "PL": 0.679, "CF": 0.67}, "secondary": {"CO": 0.578, "TW": 0.441}, "avoid": {"ME": 0.208, "SH": 0.157, "IMP": 0.07}}}}, "hardskills": {"actual_role": {"role": "Fullstack Engineer", "level": "Senior"}, "target_role": {"role": "Software Architect", "level": "Junior"}, "skills_gaps": []}, "pdp": None, "_version": 1, "_created": "2024-08-19 15:05:28.605000", "_updated": "2024-08-19 15:05:28.605000"},
        {"project_id": "662520e97836b3fb9c101525", "name": "Simon Morrow", "email": "simon.morrow@acme.com", "actual_role": {"role": "Frontend Engineer", "level": "Senior"}, "team": "PLATFORM", "phases": {"start": {"bootcamp_seminar": True}, "workstyle": {"soft_skills_workshop": True, "spi": True, "observers": True}, "skills": {"hard_skills_workshop": True, "actual_role": True, "target_role": True, "skills_gap_analysis": True, "pdp": True}}, "softskills": {"belbin": {"spi": {"primary": {"RI": 0.891, "PL": 0.849, "SH": 0.808}, "secondary": {"CF": 0.529, "SP": 0.479, "ME": 0.441, "IMP": 0.328}, "avoid": {"CO": 0.208, "TW": 0.108}}}}, "hardskills": {"actual_role": {"role": "Frontend Engineer", "level": "Senior"}, "target_role": {"role": "Frontend Engineer", "level": "Lead"}, "skills_gaps": []}, "pdp": None, "_version": 1, "_created": "2024-08-19 15:05:28.606000", "_updated": "2024-08-19 15:05:28.606000"},
        {"project_id": "662520e97836b3fb9c101525", "name": "Vincent Lawrence", "email": "vincent.lawrence@acme.com", "actual_role": {"role": "Software Engineer", "level": "Mid_Level"}, "team": "DEVOPS", "phases": {"start": {"bootcamp_seminar": True}, "workstyle": {"soft_skills_workshop": True, "spi": True, "observers": True}, "skills": {"hard_skills_workshop": True, "actual_role": True, "target_role": True, "skills_gap_analysis": True, "pdp": True}}, "softskills": {"belbin": {"spi": {"primary": {"RI": 0.92, "SP": 0.899, "PL": 0.849}, "secondary": {"SH": 0.491, "ME": 0.441, "TW": 0.291, "CO": 0.27}, "avoid": {"CF": 0.141, "IMP": 0.091}}}}, "hardskills": {"actual_role": {"role": "Software Engineer", "level": "Mid_Level"}, "target_role": {"role": "Software Engineer", "level": "Senior"}, "skills_gaps": []}, "pdp": None, "_version": 1, "_created": "2024-08-19 15:05:28.607000", "_updated": "2024-08-19 15:05:28.607000"},
        {"project_id": "662520e97836b3fb9c101525", "name": "Timothy Eaton", "email": "timothy.eaton@acme.com", "actual_role": {"role": "Frontend Engineer", "level": "Senior"}, "team": "PLATFORM", "phases": {"start": {"bootcamp_seminar": True}, "workstyle": {"soft_skills_workshop": True, "spi": True, "observers": True}, "skills": {"hard_skills_workshop": True, "actual_role": True, "target_role": True, "skills_gap_analysis": True, "pdp": True}}, "softskills": {"belbin": {"spi": {"primary": {"CF": 0.87, "ME": 0.67}, "secondary": {"PL": 0.57, "SH": 0.491, "CO": 0.457, "RI": 0.42, "SP": 0.408, "TW": 0.37, "IMP": 0.328}, "avoid": {}}}}, "hardskills": {"actual_role": {"role": "Frontend Engineer", "level": "Senior"}, "target_role": {"role": "Fullstack Engineer", "level": "Mid_Level"}, "skills_gaps": []}, "pdp": None, "_version": 1, "_created": "2024-08-19 15:05:28.607000", "_updated": "2024-08-19 15:05:28.607000"},
        {"project_id": "662520e97836b3fb9c101525", "name": "Tyler Osbourne", "email": "tyler.osbourne@acme.com", "actual_role": {"role": "Computer Vision Engineer", "level": "Mid_Level"}, "team": "DATA", "phases": {"start": {"bootcamp_seminar": True}, "workstyle": {"soft_skills_workshop": True, "spi": True, "observers": True}, "skills": {"hard_skills_workshop": True, "actual_role": True, "target_role": True, "skills_gap_analysis": True, "pdp": True}}, "softskills": {"belbin": {"spi": {"primary": {"IMP": 0.82, "PL": 0.808, "SH": 0.808}, "secondary": {"RI": 0.599, "SP": 0.479, "CF": 0.291, "ME": 0.279}, "avoid": {"TW": 0.22, "CO": 0.208}}}}, "hardskills": {"actual_role": {"role": "Computer Vision Engineer", "level": "Mid_Level"}, "target_role": {"role": "Computer Vision Engineer", "level": "Senior"}, "skills_gaps": []}, "pdp": None, "_version": 1, "_created": "2024-08-19 15:05:28.608000", "_updated": "2024-08-19 15:05:28.608000"}
    ]

    dao = MongoDAO(dbname="test-dao")

    print(f"INSERT {'-'*80}")
    for s in staff:
        print(dao.insert(table="staff", record=s))

    who = list(dao.find_by_key_value(table="staff", key="name", value="Vanesa Lomas"))[0]
    by_id = dao.find_by_id(table="staff", id = who["_id"])
    print(by_id)
    id = who["_id"].replace("staff/", "")
    by_id = dao.find_by_id(table="staff", id = id)
    print(by_id)


    # results = 02_dao.fetch(table="staff", query=[('project_id', '==', 'PADMI'),('team', '==', 'Apps')], keys=['name', 'email', 'softskills'])
    print(f"FETCH {'-'*80}")
    results = list(dao.fetch(table="staff", query=[('project_id', '==', 'PADMI'),('team', '!=', 'Apps')]))
    print(*results, sep='\n')

    print(f"FETCH {'-'*80}")
    results = dao.find_by_key_value_like(table="staff", key="project_id", value="ADM")
    # results = dao.fetch(table="staff", query=[('email', 'like', '.es'), ('name', 'like', 'Jos')], keys=['name', 'email', 'team', 'softskills'])
    print(*results, sep='\n')

    print(f"DROP {'-'*80}")
    print(dao.drop(table="staff"))
'''