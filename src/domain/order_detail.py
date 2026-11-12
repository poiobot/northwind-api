from __future__ import annotations

from typing import List, Optional, Union, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone


class OrderDetail(BaseModel):
	model_config = ConfigDict(populate_by_name=True)
	# The primary key is (OrderID, ProductID), so id is not a column: it only carries the table name
	# GenericDAO reads, and exclude=True keeps it out of the dumped record
	id: Optional[Any] = Field(default=None, exclude=True, json_schema_extra={"table": "Order Details"})
	OrderID: Union[int, "Order"] = Field(default=None, json_schema_extra={"table": "Orders"})
	ProductID: Union[int, "Product"] = Field(default=None, json_schema_extra={"table": "Products"})
	UnitPrice: float = 0.0
	Quantity: int = 1
	Discount: float = 0.0
