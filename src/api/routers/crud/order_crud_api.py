from fastapi import APIRouter, Query, HTTPException, status, Body
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi_pagination import add_pagination, paginate, LimitOffsetPage
from fastapi_pagination.paginator import paginate as paginate_raw
from fastapi_pagination.utils import disable_installed_extensions_check
from pydantic import ValidationError
from typing import List, Dict

from lib.spore_tools import SporeTools as tools
from lib.httptools import HttpTools, QueryParser
from control.crud.order_crud_ctl import OrderCrudCTL
from domain.order import Order

disable_installed_extensions_check()

router = APIRouter()
handler = OrderCrudCTL()

# Reference fields that ?expand= can replace with the referenced documents
EXPANDABLE = ("customerID", "employeeID",)
EXPAND_HELP = "Comma-separated reference fields to replace with the referenced documents: customerID, employeeID"


@router.post(path="/northwind/orders", response_model=Order, response_model_by_alias=False, status_code=status.HTTP_201_CREATED)
async def create_order(data: Dict = Body):
	try:
		data["id"] = data.get("id", None)
		order = Order(**data)
		order = handler.create(order)
		return order
	except ValidationError as e:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"incorrect input data: {data}")
	except Exception as e:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"order: {data} already exists")


@router.get(path="/northwind/orders", response_model=LimitOffsetPage[Order], response_model_by_alias=False)
async def fetch_orders(q: List[str] = Query(None), keys: str = "*", expand: str = Query(None, description=EXPAND_HELP)):
	keys = "*" if keys == "*" else {key: 1 for key in keys.split(",")}
	query = None if q is None else QueryParser.transform_query_conditions(q, Order)
	expand = HttpTools.parse_expand(expand, EXPANDABLE)
	orders = list(handler.fetch(query=query, keys=keys, expand=expand, reify=True if keys == "*" else False))
	return paginate(orders) if keys == "*" else JSONResponse(content=jsonable_encoder(orders))


@router.get(path="/northwind/orders/{id}", tags=["order"], response_model=Order, response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def find_order(id: int, expand: str = Query(None, description=EXPAND_HELP)):
	order = handler.get_by_id(id, expand=HttpTools.parse_expand(expand, EXPANDABLE))
	if order is None:
		raise HTTPException(status_code=404, detail=f"order {id} not found")
	return order


@router.put(path="/northwind/orders/{id}", tags=["order"], status_code=status.HTTP_200_OK)
async def update_order(id: int, data: Dict = Body):
	order = handler.get_by_id(id)
	if order is None:
		raise HTTPException(status_code=404, detail=f"order {id} not found")
	merged = order
	if isinstance(merged, dict):
		merged.update(data)
	else:
		merged = merged.model_dump()
		merged.update(data)
	if handler.update(id, Order(**merged)):
		return JSONResponse(content={"order": data, "status": "UPDATED"}, status_code=status.HTTP_200_OK)


@router.delete(path="/northwind/orders/{id}", tags=["order"], status_code=status.HTTP_202_ACCEPTED)
async def delete_order(id: int):
	if handler.delete(id):
		return JSONResponse(content={"order": id, "status": "DELETED"}, status_code=status.HTTP_200_OK)
	else:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"order: {id} not found")


add_pagination(router)
