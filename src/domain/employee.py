from __future__ import annotations

from typing import List, Optional, Union, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone


class Address(BaseModel):
	model_config = ConfigDict(populate_by_name=True)
	street: Optional[str] = None
	city: Optional[str] = None
	region: Optional[str] = None
	postalCode: Optional[Union[float, str]] = None
	country: Optional[str] = None
	phone: Optional[str] = None

class Employee(BaseModel):
	model_config = ConfigDict(populate_by_name=True)
	id: Optional[int] = Field(default=None, alias="_id", json_schema_extra={"table": "employees"})
	lastName: Optional[str] = None
	firstName: Optional[str] = None
	title: Optional[str] = None
	titleOfCourtesy: Optional[str] = None
	birthDate: Optional[str] = None
	hireDate: Optional[str] = None
	address: Optional[Address] = None
	notes: Optional[str] = None
	reportsTo: Optional[Union[int, str]] = None
	version: int = Field(default=1, alias="_version")
	created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="_created")
	updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="_updated")
