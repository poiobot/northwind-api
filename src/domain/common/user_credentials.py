from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional


class UserCredentials(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")
    id: str = Field(default=None, alias="user_id")
    name: str = None
    email: str = None
    roles: Optional[List[str]] = ["user"]
