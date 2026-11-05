from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone


class User(BaseModel):
	model_config = ConfigDict(populate_by_name=True)
	id: str = Field(default=None, alias='_id', json_schema_extra={"table": "users"})
	state: Optional[str] = "PENDING"
	login_type: str = "MANUAL"
	name: Optional[str] = None
	email: str = None
	password: Optional[str] = None
	profile: Optional[str] = Field(default=None, json_schema_extra={"table": "profiles"})
	code: Optional[str] = "----"
	attempts: int = 3
	version: int = Field(default=1, alias="_version")
	created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="_created")
	updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="_updated")
