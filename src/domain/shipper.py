from __future__ import annotations

from typing import List, Optional, Union, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone


class Shipper(BaseModel):
	model_config = ConfigDict(populate_by_name=True)
	id: Optional[int] = Field(default=None, alias="_id", json_schema_extra={"table": "shippers"})
	companyName: str = None
	phone: str = None
	version: int = Field(default=1, alias="_version")
	created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="_created")
	updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="_updated")
