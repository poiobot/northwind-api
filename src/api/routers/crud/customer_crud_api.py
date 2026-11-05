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
from control.crud.customer_crud_ctl import CustomerCrudCTL
from domain.customer import Customer

disable_installed_extensions_check()

router = APIRouter()
handler = CustomerCrudCTL()

# Reference fields that ?expand= can replace with the referenced documents
EXPANDABLE = ()
EXPAND_HELP = "Comma-separated reference fields to replace with the referenced documents: none"


@router.post(path="/northwind/customers", response_model=Customer, response_model_by_alias=False, status_code=status.HTTP_201_CREATED)
async def create_customer(data: Dict = Body):
	try:
		data["id"] = data.get("id", None)
		customer = Customer(**data)
		customer = handler.create(customer)
		return customer
	except ValidationError as e:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"incorrect input data: {data}")
	except Exception as e:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"customer: {data} already exists")


@router.get(path="/northwind/customers", response_model=LimitOffsetPage[Customer], response_model_by_alias=False)
async def fetch_customers(q: List[str] = Query(None), keys: str = "*", expand: str = Query(None, description=EXPAND_HELP)):
	keys = "*" if keys == "*" else {key: 1 for key in keys.split(",")}
	query = None if q is None else QueryParser.transform_query_conditions(q, Customer)
	expand = HttpTools.parse_expand(expand, EXPANDABLE)
	customers = list(handler.fetch(query=query, keys=keys, expand=expand, reify=True if keys == "*" else False))
	return paginate(customers) if keys == "*" else JSONResponse(content=jsonable_encoder(customers))


@router.get(path="/northwind/customers/{id}", tags=["customer"], response_model=Customer, response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def find_customer(id: str, expand: str = Query(None, description=EXPAND_HELP)):
	customer = handler.get_by_id(id, expand=HttpTools.parse_expand(expand, EXPANDABLE))
	if customer is None:
		raise HTTPException(status_code=404, detail=f"customer {id} not found")
	return customer


@router.put(path="/northwind/customers/{id}", tags=["customer"], status_code=status.HTTP_200_OK)
async def update_customer(id: str, data: Dict = Body):
	customer = handler.get_by_id(id)
	if customer is None:
		raise HTTPException(status_code=404, detail=f"customer {id} not found")
	merged = customer
	if isinstance(merged, dict):
		merged.update(data)
	else:
		merged = merged.model_dump()
		merged.update(data)
	if handler.update(id, Customer(**merged)):
		return JSONResponse(content={"customer": data, "status": "UPDATED"}, status_code=status.HTTP_200_OK)


@router.delete(path="/northwind/customers/{id}", tags=["customer"], status_code=status.HTTP_202_ACCEPTED)
async def delete_customer(id: str):
	if handler.delete(id):
		return JSONResponse(content={"customer": id, "status": "DELETED"}, status_code=status.HTTP_200_OK)
	else:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"customer: {id} not found")


add_pagination(router)
