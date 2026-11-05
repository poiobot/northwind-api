from __future__ import annotations

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Union, TYPE_CHECKING
from datetime import datetime, timezone

if TYPE_CHECKING:
	from domain.common.media import Media

class Profile(BaseModel):
	model_config = ConfigDict(populate_by_name=True, extra="allow")
	id: str = Field(default=None, alias='_id', json_schema_extra={"table": "profiles"})
	name: Optional[str] = None
	email: Optional[str] = None
	phone: Optional[str] = None
	avatar: Optional[Union[str,"Media"]] = Field(default=None, json_schema_extra={"table": "media"}) 
	roles: List[str] = ["user"]
	version: int = Field(default=1, alias="_version")
	created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="_created")
	updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="_updated")






