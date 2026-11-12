from __future__ import annotations

from typing import List, Optional, Union, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone


class Order(BaseModel):
	model_config = ConfigDict(populate_by_name=True)
	id: Optional[int] = Field(default=None, alias="OrderID", json_schema_extra={"table": "Orders"})
	CustomerID: Optional[Union[str, "Customer"]] = Field(default=None, json_schema_extra={"table": "Customers"})
	EmployeeID: Optional[Union[int, "Employee"]] = Field(default=None, json_schema_extra={"table": "Employees"})
	OrderDate: Optional[datetime] = None
	RequiredDate: Optional[datetime] = None
	ShippedDate: Optional[datetime] = None
	ShipVia: Optional[Union[int, "Shipper"]] = Field(default=None, json_schema_extra={"table": "Shippers"})
	Freight: Optional[float] = 0.0
	ShipName: Optional[str] = None
	ShipAddress: Optional[str] = None
	ShipCity: Optional[str] = None
	ShipRegion: Optional[str] = None
	ShipPostalCode: Optional[str] = None
	ShipCountry: Optional[str] = None
