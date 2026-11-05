"""?q=OPERATOR(field,value) filters on generated list routes (QueryParser)."""
from typing import List, Optional, Union

import pytest
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from lib.httptools import QueryParser


class Address(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    city: str = None
    postalCode: Union[float, str] = None


class Order(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: Optional[int] = Field(default=None, alias="_id", json_schema_extra={"table": "orders"})


class OrderLine(BaseModel):
    """Shaped like generated northwind models: an int reference, numbers, mixed and nested fields."""
    model_config = ConfigDict(populate_by_name=True)
    id: Optional[int] = Field(default=None, alias="_id", json_schema_extra={"table": "order_lines"})
    OrderID: Union[int, Order] = Field(default=None, json_schema_extra={"table": "orders"})
    customerID: str = None
    Quantity: int = 0
    UnitPrice: float = 0.0
    discontinued: bool = None
    reportsTo: Union[int, str] = None
    address: Address = None
    tags: List[str] = None
    version: int = Field(default=1, alias="_version")


def parse(*conditions):
    return QueryParser.transform_query_conditions(list(conditions), OrderLine)


@pytest.mark.parametrize("condition, expected", [
    ("EQ(OrderID,10248)", ("OrderID", "==", 10248)),
    ("GT(Quantity,100)", ("Quantity", ">", 100)),
    ("LTE(UnitPrice,14.5)", ("UnitPrice", "<=", 14.5)),
    ("EQ(discontinued,true)", ("discontinued", "==", True)),
    ("EQ(customerID,VINET)", ("customerID", "==", "VINET")),
    ("EQ(reportsTo,2)", ("reportsTo", "==", 2)),
    ("EQ(reportsTo,NULL)", ("reportsTo", "==", "NULL")),
    ("EQ(address.city,Berlin)", ("address.city", "==", "Berlin")),
    ("EQ(address.postalCode,12209)", ("address.postalCode", "==", 12209.0)),
    ("EQ(id,10248)", ("_id", "==", 10248)),
    ("EQ(_id,10248)", ("_id", "==", 10248)),
    ("LIKE(customerID,VIN)", ("customerID", "like", "VIN")),
    ("EQ(tags,beverages)", ("tags", "==", "beverages")),
    ("IN(OrderID,10248|10249)", ("OrderID", "in", [10248, 10249])),
    ("NOT-IN(OrderID,10248)", ("OrderID", "not-in", [10248])),
    ("EQ(notInTheModel,5)", ("notInTheModel", "==", "5")),
])
def test_conditions_become_typed_dao_conditions(condition, expected):
    assert parse(condition) == [expected]


def test_conditions_combine():
    assert parse("EQ(OrderID,10248)", "GT(Quantity,10)") == [("OrderID", "==", 10248), ("Quantity", ">", 10)]


@pytest.mark.parametrize("condition", ["EQ(OrderID)", "FOO(OrderID,1)", "garbage", "EQ(OrderID,abc)", "IN(Quantity,1|two)"])
def test_unusable_conditions_are_a_422(condition):
    with pytest.raises(HTTPException) as error:
        parse(condition)
    assert error.value.status_code == 422
    assert error.value.detail[0]["loc"] == ["query", "q"] and error.value.detail[0]["input"] == condition


def test_without_a_model_values_stay_text():
    assert QueryParser.transform_query_conditions(["EQ(OrderID,10248)", "IN(a,1|2)"]) == [
        ("OrderID", "==", "10248"), ("a", "in", ["1", "2"])]
