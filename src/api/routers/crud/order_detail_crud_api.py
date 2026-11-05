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
from control.crud.order_detail_crud_ctl import OrderDetailCrudCTL
from domain.order_detail import OrderDetail

disable_installed_extensions_check()

router = APIRouter()
handler = OrderDetailCrudCTL()

# Reference fields that ?expand= can replace with the referenced documents
EXPANDABLE = ("OrderID", "ProductID",)
EXPAND_HELP = "Comma-separated reference fields to replace with the referenced documents: OrderID, ProductID"


@router.post(path="/northwind/order_details", response_model=OrderDetail, response_model_by_alias=False, status_code=status.HTTP_201_CREATED)
async def create_order_detail(data: Dict = Body):
	try:
		data["id"] = data.get("id", None)
		order_detail = OrderDetail(**data)
		order_detail = handler.create(order_detail)
		return order_detail
	except ValidationError as e:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"incorrect input data: {data}")
	except Exception as e:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"order_detail: {data} already exists")


@router.get(path="/northwind/order_details", response_model=LimitOffsetPage[OrderDetail], response_model_by_alias=False)
async def fetch_order_details(q: List[str] = Query(None), keys: str = "*", expand: str = Query(None, description=EXPAND_HELP)):
	keys = "*" if keys == "*" else {key: 1 for key in keys.split(",")}
	query = None if q is None else QueryParser.transform_query_conditions(q, OrderDetail)
	expand = HttpTools.parse_expand(expand, EXPANDABLE)
	order_details = list(handler.fetch(query=query, keys=keys, expand=expand, reify=True if keys == "*" else False))
	return paginate(order_details) if keys == "*" else JSONResponse(content=jsonable_encoder(order_details))


@router.get(path="/northwind/order_details/{id}", tags=["order_detail"], response_model=OrderDetail, response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def find_order_detail(id: int, expand: str = Query(None, description=EXPAND_HELP)):
	order_detail = handler.get_by_id(id, expand=HttpTools.parse_expand(expand, EXPANDABLE))
	if order_detail is None:
		raise HTTPException(status_code=404, detail=f"order_detail {id} not found")
	return order_detail


@router.put(path="/northwind/order_details/{id}", tags=["order_detail"], status_code=status.HTTP_200_OK)
async def update_order_detail(id: int, data: Dict = Body):
	order_detail = handler.get_by_id(id)
	if order_detail is None:
		raise HTTPException(status_code=404, detail=f"order_detail {id} not found")
	merged = order_detail
	if isinstance(merged, dict):
		merged.update(data)
	else:
		merged = merged.model_dump()
		merged.update(data)
	if handler.update(id, OrderDetail(**merged)):
		return JSONResponse(content={"order_detail": data, "status": "UPDATED"}, status_code=status.HTTP_200_OK)


@router.delete(path="/northwind/order_details/{id}", tags=["order_detail"], status_code=status.HTTP_202_ACCEPTED)
async def delete_order_detail(id: int):
	if handler.delete(id):
		return JSONResponse(content={"order_detail": id, "status": "DELETED"}, status_code=status.HTTP_200_OK)
	else:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"order_detail: {id} not found")


add_pagination(router)
