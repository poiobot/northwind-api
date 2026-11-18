"""SqlAlchemyDAO against plain SQL schemas like Northwind, and against Spore-shaped tables.

Plain schemas have integer keys the database assigns, composite keys, table names with
spaces, and none of Spore's _version/_created/_updated/_state columns. Spore-shaped
tables (a text _id plus those columns) must keep working as before.

Tables copied from MongoDB (database/sqlite/northwind_spore.db) keep embedded documents and
arrays in JSON columns, which must read back as dicts and lists. expand must put the
referenced row under the reference field, as MongoDAO does, instead of merging the two rows.
"""
import sqlite3
from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from api import settings
from services.database.impl.sqlalchemy_dao import SqlAlchemyDAO

SCHEMA = """
CREATE TABLE Shippers (ShipperID INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, CompanyName TEXT NOT NULL, Phone TEXT);
INSERT INTO Shippers VALUES (1, 'Speedy Express', '(503) 555-9831'), (2, 'United Package', '(503) 555-3199');

CREATE TABLE Orders (OrderID INTEGER PRIMARY KEY, ShipVia INTEGER REFERENCES Shippers (ShipperID));
INSERT INTO Orders VALUES (10248, 2);

CREATE TABLE OrderLines (OrderID INTEGER NOT NULL, ProductID INTEGER NOT NULL, Quantity INTEGER,
                         PRIMARY KEY (OrderID, ProductID));
INSERT INTO OrderLines VALUES (10248, 11, 12), (10248, 42, 10), (10249, 14, 9);

CREATE TABLE "Order Details" (OrderID INTEGER NOT NULL, ProductID INTEGER NOT NULL, Quantity INTEGER,
                              PRIMARY KEY (OrderID, ProductID));
INSERT INTO "Order Details" VALUES (10248, 11, 12), (10248, 42, 10), (10249, 14, 9);

CREATE TABLE notes (_id TEXT PRIMARY KEY, text TEXT, _version INTEGER, _created TEXT, _updated TEXT, _state TEXT);
INSERT INTO notes VALUES ('n1', 'hello', 1, '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00', NULL);
"""

# Shaped like database/sqlite/northwind_spore.db: every table keyed by _id, JSON columns.
SPORE_SCHEMA = """
CREATE TABLE customers (_id TEXT PRIMARY KEY NOT NULL, companyName TEXT, address JSON);
INSERT INTO customers VALUES ('VINET', 'Vins et alcools Chevalier', '{"city": "Reims", "postalCode": 51100}'),
                             ('PARIS', 'Paris spécialités', NULL);

CREATE TABLE employees (_id INTEGER PRIMARY KEY, lastName TEXT, reportsTo INTEGER, mentors JSON);
INSERT INTO employees VALUES (2, 'Fuller', 'NULL', NULL), (5, 'Buchanan', 2, '[2]'), (6, 'Suyama', 5, '[5, 999, 2, 5]');

CREATE TABLE orders (_id INTEGER PRIMARY KEY, customerID TEXT, employeeID INTEGER, shipAddress JSON);
INSERT INTO orders VALUES (10248, 'VINET', 5, '{"city": "Reims"}'), (10249, 'PARIS', 6, NULL), (10250, 'GONE', 2, NULL);

CREATE TABLE categories (_id INTEGER PRIMARY KEY, name TEXT, description TEXT);
INSERT INTO categories VALUES (4, 'Dairy Products', 'Cheeses');

CREATE TABLE products (_id INTEGER PRIMARY KEY, name TEXT, categoryID INTEGER);
INSERT INTO products VALUES (11, 'Queso Cabrales', 4), (99, 'Uncategorised', NULL);
"""


@pytest.fixture
def path(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DB_CONNECTION_STRING", None)
    db = tmp_path / "northwind.db"
    con = sqlite3.connect(db)
    con.executescript(SCHEMA)
    con.close()
    return db


@pytest.fixture
def dao(path):
    dao = SqlAlchemyDAO(dbname=str(path), dbtype="sqlite")
    yield dao
    dao.engine.dispose()


@pytest.fixture
def spore(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DB_CONNECTION_STRING", None)
    db = tmp_path / "northwind_spore.db"
    con = sqlite3.connect(db)
    con.executescript(SPORE_SCHEMA)
    con.close()
    dao = SqlAlchemyDAO(dbname=str(db), dbtype="sqlite")
    yield dao
    dao.engine.dispose()


def rows(path, sql, *args):
    """Read the database directly, without going through SqlAlchemyDAO."""
    con = sqlite3.connect(path)
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


# Reads that already work keep working.

def test_find_by_id_returns_the_row_for_an_integer_key(dao):
    assert dao.find_by_id("Shippers", 2) == {"ShipperID": 2, "CompanyName": "United Package", "Phone": "(503) 555-3199"}


# JSON columns hold embedded documents and arrays; reads give them back as dicts and lists.

def test_find_by_id_reads_a_json_column_as_a_dict(spore):
    assert spore.find_by_id("customers", "VINET")["address"] == {"city": "Reims", "postalCode": 51100}


def test_fetch_reads_json_columns_as_lists_and_null_as_none(spore):
    found = spore.fetch("employees", keys=["_id", "mentors"], sort_by=[("_id", 1)])
    assert found == [{"_id": 2, "mentors": None}, {"_id": 5, "mentors": [2]}, {"_id": 6, "mentors": [5, 999, 2, 5]}]


def test_a_dict_inserted_into_a_json_column_reads_back_as_the_same_dict(spore):
    address = {"street": "Obere Str. 57", "city": "Berlin", "postalCode": 12209}
    spore.insert("customers", {"_id": "ALFKI", "companyName": "Alfreds Futterkiste", "address": address})
    assert spore.find_by_id("customers", "ALFKI")["address"] == address


def test_update_of_a_json_column_returns_the_new_dict(spore):
    address = {"city": "Paris", "postalCode": 75012}
    assert spore.update("customers", "PARIS", {"address": address})["address"] == address


# expand puts the referenced row under the reference field, as MongoDAO's $lookup + $unwind does.

def references(field, table, is_array=False):
    """The meta GenericDAO passes for an entity with this one reference field."""
    return {"references": {field: {"table": table, "is_array": is_array}}}


def test_expand_puts_the_referenced_row_under_the_field(dao):
    order = dao.fetch("Orders", expand=["ShipVia"], meta={"references": {"ShipVia": {"table": "Shippers"}}})[0]
    assert order == {"OrderID": 10248,
                     "ShipVia": {"ShipperID": 2, "CompanyName": "United Package", "Phone": "(503) 555-3199"}}


def test_expand_keeps_the_row_own_columns_when_both_tables_share_column_names(spore):
    product = spore.find_by_id("products", 11, expand=["categoryID"], meta=references("categoryID", "categories"))
    assert product == {"_id": 11, "name": "Queso Cabrales",
                       "categoryID": {"_id": 4, "name": "Dairy Products", "description": "Cheeses"}}


def test_expand_reads_json_columns_of_the_row_and_of_the_referenced_row(spore):
    order = spore.find_by_id("orders", 10248, expand=["customerID"], meta=references("customerID", "customers"))
    assert order["shipAddress"] == {"city": "Reims"}
    assert order["customerID"] == {"_id": "VINET", "companyName": "Vins et alcools Chevalier",
                                   "address": {"city": "Reims", "postalCode": 51100}}


def test_expand_follows_a_reference_to_the_same_table(spore):
    employee = spore.find_by_id("employees", 6, expand=["reportsTo"], meta=references("reportsTo", "employees"))
    assert (employee["_id"], employee["lastName"]) == (6, "Suyama")
    assert employee["reportsTo"] == {"_id": 5, "lastName": "Buchanan", "reportsTo": 2, "mentors": [2]}


@pytest.mark.parametrize("table, id, field, target", [
    ("products", 99, "categoryID", "categories"),  # NULL
    ("orders", 10250, "customerID", "customers"),  # 'GONE' is no customer
    ("employees", 2, "reportsTo", "employees"),  # the string 'NULL', as in Northwind
], ids=["null", "dangling", "string NULL"])
def test_expand_leaves_out_a_reference_that_matches_no_row(spore, table, id, field, target):
    # MongoDAO's $unwind (preserveNullAndEmptyArrays) drops the field when $lookup finds nothing.
    found = spore.find_by_id(table, id, expand=[field], meta=references(field, target))
    assert found["_id"] == id and field not in found


def test_expand_on_fetch_gives_each_row_its_own_referenced_row(spore):
    spore.expand_batch = 2  # three employees take two queries
    orders = spore.fetch("orders", expand=["employeeID"], sort_by=[("_id", 1)],
                       meta=references("employeeID", "employees"))
    assert [(order["_id"], order["employeeID"]["lastName"]) for order in orders] == [
        (10248, "Buchanan"), (10249, "Suyama"), (10250, "Fuller")]


def test_expand_of_a_list_of_references_gives_the_rows_found_in_list_order(spore):
    employee = spore.find_by_id("employees", 6, expand=["mentors"],
                              meta=references("mentors", "employees", is_array=True))
    assert [mentor["_id"] for mentor in employee["mentors"]] == [5, 2]  # 999 is no employee; 5 comes once


def test_expand_of_a_null_list_of_references_gives_an_empty_list(spore):
    employee = spore.find_by_id("employees", 2, expand=["mentors"],
                              meta=references("mentors", "employees", is_array=True))
    assert employee["mentors"] == []


def test_expand_skips_a_reference_that_keys_leave_out(spore):
    product = spore.find_by_id("products", 11, keys=["_id", "name"], expand=["categoryID"],
                             meta=references("categoryID", "categories"))
    assert product == {"_id": 11, "name": "Queso Cabrales"}


# Table names with spaces are quoted.

def test_fetch_filters_sorts_and_projects_a_table_whose_name_has_a_space(dao):
    found = dao.fetch("Order Details", query=[("Quantity", ">", 9)], sort_by=[("Quantity", -1)],
                      keys=["ProductID", "Quantity"])
    assert found == [{"ProductID": 11, "Quantity": 12}, {"ProductID": 42, "Quantity": 10}]


def test_distinct_reads_a_table_whose_name_has_a_space(dao):
    assert sorted(dao.distinct("Order Details", "OrderID")) == [10248, 10249]


def test_insert_into_a_table_whose_name_has_a_space(dao, path):
    dao.insert("Order Details", {"OrderID": 10250, "ProductID": 41, "Quantity": 10})
    assert rows(path, 'SELECT Quantity FROM "Order Details" WHERE OrderID = 10250 AND ProductID = 41') == [(10,)]


def test_delete_many_removes_matching_rows_from_a_table_whose_name_has_a_space(dao, path):
    assert dao.delete_many("Order Details", query=[("OrderID", "==", 10248)], physical_delete=True) == 2
    assert rows(path, 'SELECT OrderID, ProductID FROM "Order Details"') == [(10249, 14)]


def test_delete_all_empties_a_table_whose_name_has_a_space(dao, path):
    assert dao.delete_all("Order Details", physical_delete=True) == 3
    assert rows(path, 'SELECT count(*) FROM "Order Details"') == [(0,)]


# Composite keys: a row is addressed by its whole key, never by the first column alone.

@pytest.mark.parametrize("key", [{"OrderID": 10248, "ProductID": 42}, (10248, 42)], ids=["dict", "tuple"])
def test_find_by_id_accepts_a_whole_composite_key(dao, key):
    assert dao.find_by_id("OrderLines", key) == {"OrderID": 10248, "ProductID": 42, "Quantity": 10}


def test_find_by_id_with_one_value_for_a_composite_key_raises(dao):
    with pytest.raises(ValueError, match="OrderID, ProductID"):
        dao.find_by_id("OrderLines", 10248)


def test_fetch_by__id_on_a_composite_key_raises(dao):
    with pytest.raises(ValueError, match="OrderID, ProductID"):
        dao.fetch("OrderLines", query=[("_id", "==", 10248)])


def test_update_by_composite_key_changes_only_that_row(dao, path):
    dao.update("OrderLines", {"OrderID": 10248, "ProductID": 42}, {"Quantity": 99})
    assert rows(path, "SELECT OrderID, ProductID, Quantity FROM OrderLines ORDER BY 1, 2") == [
        (10248, 11, 12), (10248, 42, 99), (10249, 14, 9)]


def test_delete_by_composite_key_removes_only_that_row(dao, path):
    assert dao.delete("OrderLines", {"OrderID": 10248, "ProductID": 11}) is True
    assert rows(path, "SELECT OrderID, ProductID FROM OrderLines ORDER BY 1, 2") == [(10248, 42), (10249, 14)]


def test_delete_with_one_value_for_a_composite_key_raises_and_deletes_nothing(dao, path):
    with pytest.raises(ValueError, match="OrderID, ProductID"):
        dao.delete("OrderLines", 10248)
    assert rows(path, "SELECT count(*) FROM OrderLines") == [(3,)]


# Writes on tables without Spore's bookkeeping columns.

def test_insert_into_a_plain_table_stores_the_row_under_the_key_the_database_assigns(dao, path):
    # Shaped like GenericDAO's model_dump(by_alias=True): _id unset, bookkeeping fields filled in.
    now = datetime(2026, 11, 5, tzinfo=timezone.utc)
    stored = dao.insert("Shippers", {"_id": None, "CompanyName": "Federal Shipping", "Phone": "(503) 555-9931",
                                     "_version": 1, "_created": now, "_updated": now})
    assert stored["ShipperID"] == 3
    assert rows(path, "SELECT ShipperID, CompanyName, Phone FROM Shippers WHERE ShipperID = 3") == [
        (3, "Federal Shipping", "(503) 555-9931")]


def test_update_on_a_plain_table_changes_the_row(dao, path):
    updated = dao.update("Shippers", 1, {"Phone": "(503) 555-0000"})
    assert updated["Phone"] == "(503) 555-0000"
    assert rows(path, "SELECT Phone FROM Shippers WHERE ShipperID = 1") == [("(503) 555-0000",)]


def test_upsert_of_an_existing_row_in_a_plain_table_updates_it(dao, path):
    dao.upsert("Shippers", {"ShipperID": 2, "CompanyName": "United Package", "Phone": "(503) 555-1111"})
    assert rows(path, "SELECT Phone FROM Shippers WHERE ShipperID = 2") == [("(503) 555-1111",)]


def test_upsert_of_a_new_row_in_a_plain_table_inserts_it(dao, path):
    dao.upsert("Shippers", {"CompanyName": "Federal Shipping", "Phone": "(503) 555-9931"})
    assert rows(path, "SELECT ShipperID, CompanyName FROM Shippers WHERE ShipperID = 3") == [(3, "Federal Shipping")]


@pytest.mark.parametrize("soft_delete", [
    lambda dao: dao.delete("Shippers", 1, physical_delete=False),
    lambda dao: dao.delete_objects_list("Shippers", [1], physical_delete=False),
    lambda dao: dao.delete_many("Shippers", query=[("ShipperID", "==", 1)]),
    lambda dao: dao.delete_all("Shippers"),
], ids=["delete", "delete_objects_list", "delete_many", "delete_all"])
def test_soft_delete_on_a_table_without__state_raises_and_deletes_nothing(dao, path, soft_delete):
    with pytest.raises(ValueError, match="_state"):
        soft_delete(dao)
    assert rows(path, "SELECT count(*) FROM Shippers") == [(2,)]


# Spore-shaped tables keep their bookkeeping.

def test_insert_into_a_spore_table_generates_a_uuid_and_bookkeeping(dao, path):
    stored = dao.insert("notes", {"text": "new"})
    assert len(stored["_id"]) == 36
    assert rows(path, "SELECT text, _version, _created IS NOT NULL FROM notes WHERE _id = ?", stored["_id"]) == [
        ("new", 1, 1)]


def test_update_on_a_spore_table_bumps_the_version_and_updated_time(dao, path):
    dao.update("notes", "n1", {"text": "edited"})
    assert rows(path, "SELECT text, _version, _updated > '2026-01-01T00:00:00+00:00' FROM notes WHERE _id = 'n1'") == [
        ("edited", 2, 1)]


def test_update_of_a_missing_row_returns_none(dao):
    assert dao.update("notes", "missing", {"text": "x"}) is None


def test_soft_delete_on_a_spore_table_marks_the_row_deleted(dao, path):
    assert dao.delete("notes", "n1", physical_delete=False) is True
    assert rows(path, "SELECT _state FROM notes WHERE _id = 'n1'") == [("DELETED",)]


# Failed writes raise instead of returning None.

def test_inserting_a_duplicate_key_raises(dao):
    with pytest.raises(IntegrityError):
        dao.insert("Shippers", {"ShipperID": 1, "CompanyName": "Duplicate"})


def test_a_failed_update_raises(dao):
    with pytest.raises(SQLAlchemyError):
        dao.update("Shippers", 1, {"NoSuchColumn": 1})


def test_a_failed_upsert_raises(dao):
    with pytest.raises(SQLAlchemyError):
        dao.upsert("Shippers", {"ShipperID": 1, "NoSuchColumn": 1})
