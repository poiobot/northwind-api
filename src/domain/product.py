from __future__ import annotations

from typing import List, Optional, Union, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, timezone


class Product(BaseModel):
	model_config = ConfigDict(populate_by_name=True)
	id: Optional[int] = Field(default=None, alias="ProductID", json_schema_extra={"table": "Products"})
	ProductName: str = None
	SupplierID: Optional[Union[int, "Supplier"]] = Field(default=None, json_schema_extra={"table": "Suppliers"})
	CategoryID: Optional[Union[int, "Category"]] = Field(default=None, json_schema_extra={"table": "Categories"})
	QuantityPerUnit: Optional[str] = None
	UnitPrice: Optional[float] = 0.0
	UnitsInStock: Optional[int] = 0
	UnitsOnOrder: Optional[int] = 0
	ReorderLevel: Optional[int] = 0
	Discontinued: str = "0"
