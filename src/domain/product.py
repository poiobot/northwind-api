from __future__ import annotations

from typing import List, Optional, Union, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone


class Product(BaseModel):
	model_config = ConfigDict(populate_by_name=True)
	id: Optional[int] = Field(default=None, alias="_id", json_schema_extra={"table": "products"})
	supplierID: Union[int, "Supplier"] = Field(default=None, json_schema_extra={"table": "suppliers"})
	categoryID: Union[int, "Category"] = Field(default=None, json_schema_extra={"table": "categories"})
	quantityPerUnit: str = None
	unitPrice: float = 0.0
	unitsInStock: int = 0
	unitsOnOrder: int = 0
	reorderLevel: int = 0
	discontinued: bool = None
	name: str = None
	version: int = Field(default=1, alias="_version")
	created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="_created")
	updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="_updated")
