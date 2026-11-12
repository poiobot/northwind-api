from __future__ import annotations

from typing import List, Optional, Union, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone


class Shipper(BaseModel):
	model_config = ConfigDict(populate_by_name=True)
	id: Optional[int] = Field(default=None, alias="ShipperID", json_schema_extra={"table": "Shippers"})
	CompanyName: str = None
	Phone: Optional[str] = None
