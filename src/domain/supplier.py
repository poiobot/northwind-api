from __future__ import annotations

from typing import List, Optional, Union, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone


class Supplier(BaseModel):
	model_config = ConfigDict(populate_by_name=True)
	id: Optional[int] = Field(default=None, alias="SupplierID", json_schema_extra={"table": "Suppliers"})
	CompanyName: str = None
	ContactName: Optional[str] = None
	ContactTitle: Optional[str] = None
	Address: Optional[str] = None
	City: Optional[str] = None
	Region: Optional[str] = None
	PostalCode: Optional[str] = None
	Country: Optional[str] = None
	Phone: Optional[str] = None
	Fax: Optional[str] = None
	HomePage: Optional[str] = None
