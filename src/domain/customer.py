from __future__ import annotations

from typing import List, Optional, Union, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone


class Customer(BaseModel):
	model_config = ConfigDict(populate_by_name=True)
	id: Optional[str] = Field(default=None, alias="CustomerID", json_schema_extra={"table": "Customers"})
	CompanyName: Optional[str] = None
	ContactName: Optional[str] = None
	ContactTitle: Optional[str] = None
	Address: Optional[str] = None
	City: Optional[str] = None
	Region: Optional[str] = None
	PostalCode: Optional[str] = None
	Country: Optional[str] = None
	Phone: Optional[str] = None
	Fax: Optional[str] = None
