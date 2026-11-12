from __future__ import annotations

from typing import List, Optional, Union, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import date, datetime, timezone


class Employee(BaseModel):
	model_config = ConfigDict(populate_by_name=True, ser_json_bytes="base64")  # Photo (a JPEG) goes to JSON as URL-safe base64
	id: Optional[int] = Field(default=None, alias="EmployeeID", json_schema_extra={"table": "Employees"})
	LastName: Optional[str] = None
	FirstName: Optional[str] = None
	Title: Optional[str] = None
	TitleOfCourtesy: Optional[str] = None
	BirthDate: Optional[date] = None
	HireDate: Optional[date] = None
	Address: Optional[str] = None
	City: Optional[str] = None
	Region: Optional[str] = None
	PostalCode: Optional[str] = None
	Country: Optional[str] = None
	HomePhone: Optional[str] = None
	Extension: Optional[str] = None
	Photo: Optional[bytes] = None
	Notes: Optional[str] = None
	ReportsTo: Optional[Union[int, "Employee"]] = Field(default=None, json_schema_extra={"table": "Employees"})
	PhotoPath: Optional[str] = None
