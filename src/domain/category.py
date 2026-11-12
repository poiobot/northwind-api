from __future__ import annotations

from typing import List, Optional, Union, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone


class Category(BaseModel):
	model_config = ConfigDict(populate_by_name=True, ser_json_bytes="base64")  # Picture (a JPEG) goes to JSON as URL-safe base64
	id: Optional[int] = Field(default=None, alias="CategoryID", json_schema_extra={"table": "Categories"})
	CategoryName: Optional[str] = None
	Description: Optional[str] = None
	Picture: Optional[bytes] = None
