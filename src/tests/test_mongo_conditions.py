"""MongoDAO query conditions: every condition applies, including several on one field."""
import uuid

import pytest
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from services.database.impl.mongo_dao import MongoDAO


@pytest.fixture
def dao():
    client = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=1000)
    try:
        client.admin.command("ping")
    except PyMongoError:
        client.close()
        pytest.skip("needs MongoDB on localhost:27017")
    dbname = f"spore_test_{uuid.uuid4().hex[:8]}"
    dao = MongoDAO(dbname)
    dao.db["lines"].insert_many([{"_id": i, "Quantity": q} for i, q in enumerate([5, 15, 25])])
    yield dao
    client.drop_database(dbname)
    dao.handler.close()
    client.close()


def test_conditions_on_one_field_all_apply(dao):
    found = dao.fetch("lines", query=[("Quantity", ">", 10), ("Quantity", "<", 20)])
    assert [d["Quantity"] for d in found] == [15]


def test_delete_many_honours_every_condition(dao):
    dao.delete_many("lines", query=[("Quantity", ">", 10), ("Quantity", "<", 20)], physical_delete=True)
    assert sorted(d["Quantity"] for d in dao.db["lines"].find()) == [5, 25]
