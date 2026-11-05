from pydantic import BaseModel, HttpUrl, Field, field_validator
from datetime import datetime, timezone
from typing import List, Dict, Union, Optional, Any
from bson.objectid import ObjectId


class Media(BaseModel):
    class Config:
        populate_by_name = True
    id: str = Field(default_factory=lambda: str(ObjectId()), alias='_id', table="media")
    owner: str= Field(default=None, table="profiles")
    type: str = "BINARY"
    volume: str = None
    oid: str = None
    url: Optional[str] = None
    _created: datetime = datetime.now(timezone.utc)
    _updated: datetime = datetime.now(timezone.utc)
