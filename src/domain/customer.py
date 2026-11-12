from __future__ import annotations

from typing import List, Optional, Union, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone


class Address(BaseModel):
	model_config = ConfigDict(populate_by_name=True)
	street: str = None
	city: str = None
	region: str = None
	postalCode: Union[float, str] = None
	country: str = None
	phone: str = None

class Customer(BaseModel):
	model_config = ConfigDict(populate_by_name=True)
	id: Optional[str] = Field(default=None, alias="CustomerID", json_schema_extra={"table": "customers"})
	companyName: str = None
	contactName: str = None
	contactTitle: str = None
	address: Address = None
	version: int = Field(default=1, alias="_version")
	created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="_created")
	updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="_updated")
