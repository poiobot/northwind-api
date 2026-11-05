from __future__ import annotations

from typing import List, Optional, Union, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone


class OrderDetail(BaseModel):
	model_config = ConfigDict(populate_by_name=True)
	id: Optional[int] = Field(default=None, alias="_id", json_schema_extra={"table": "order_details"})
	OrderID: Union[int, "Order"] = Field(default=None, json_schema_extra={"table": "orders"})
	ProductID: Union[int, "Product"] = Field(default=None, json_schema_extra={"table": "products"})
	UnitPrice: float = 0.0
	Quantity: int = 0
	Discount: float = 0.0
	version: int = Field(default=1, alias="_version")
	created: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="_created")
	updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="_updated")
