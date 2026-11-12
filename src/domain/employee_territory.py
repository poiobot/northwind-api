from __future__ import annotations

from typing import List, Optional, Union, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone


class EmployeeTerritory(BaseModel):
	model_config = ConfigDict(populate_by_name=True)
	# The primary key is (EmployeeID, TerritoryID), so id is not a column: it only carries the table name
	# GenericDAO reads, and exclude=True keeps it out of the dumped record
	id: Optional[Any] = Field(default=None, exclude=True, json_schema_extra={"table": "EmployeeTerritories"})
	EmployeeID: Union[int, "Employee"] = Field(default=None, json_schema_extra={"table": "Employees"})
	TerritoryID: str = Field(default=None, json_schema_extra={"table": "Territories"})
