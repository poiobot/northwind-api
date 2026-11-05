from __future__ import annotations

from typing import List, Optional, Union, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone


class Shipaddress(BaseModel):
	model_config = ConfigDict(populate_by_name=True)
	street: str = None
	city: str = None
	region: str = None
	postalCode: Union[float, str] = None
	country: str = None

class Order(BaseModel):
	model_config = ConfigDict(populate_by_name=True)
	id: Optional[int] = Field(default=None, alias="_id", json_schema_extra={"table": "orders"})
	customerID: Union[str, "Customer"] = Field(default=None, json_schema_extra={"table": "customers"})
	employeeID: Union[int, "Employee"] = Field(default=None, json_schema_extra={"table": "employees"})
	orderDate: str = None
	requiredDate: str = None
	shippedDate: str = None
	shipVia: int = 0
	freight: float = 0.0
	shipName: str = None
	shipAddress: Shipaddress = None
	version: int = Field(default=1, alias="_version")
	created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="_created")
	updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="_updated")
