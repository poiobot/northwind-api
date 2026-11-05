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
from control.crud.supplier_crud_ctl import SupplierCrudCTL
from domain.supplier import Supplier

disable_installed_extensions_check()

router = APIRouter()
handler = SupplierCrudCTL()

# Reference fields that ?expand= can replace with the referenced documents
EXPANDABLE = ()
EXPAND_HELP = "Comma-separated reference fields to replace with the referenced documents: none"


@router.post(path="/northwind/suppliers", response_model=Supplier, response_model_by_alias=False, status_code=status.HTTP_201_CREATED)
async def create_supplier(data: Dict = Body):
	try:
		data["id"] = data.get("id", None)
		supplier = Supplier(**data)
		supplier = handler.create(supplier)
		return supplier
	except ValidationError as e:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"incorrect input data: {data}")
	except Exception as e:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"supplier: {data} already exists")


@router.get(path="/northwind/suppliers", response_model=LimitOffsetPage[Supplier], response_model_by_alias=False)
async def fetch_suppliers(q: List[str] = Query(None), keys: str = "*", expand: str = Query(None, description=EXPAND_HELP)):
	keys = "*" if keys == "*" else {key: 1 for key in keys.split(",")}
	query = None if q is None else QueryParser.transform_query_conditions(q, Supplier)
	expand = HttpTools.parse_expand(expand, EXPANDABLE)
	suppliers = list(handler.fetch(query=query, keys=keys, expand=expand, reify=True if keys == "*" else False))
	return paginate(suppliers) if keys == "*" else JSONResponse(content=jsonable_encoder(suppliers))


@router.get(path="/northwind/suppliers/{id}", tags=["supplier"], response_model=Supplier, response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def find_supplier(id: int, expand: str = Query(None, description=EXPAND_HELP)):
	supplier = handler.get_by_id(id, expand=HttpTools.parse_expand(expand, EXPANDABLE))
	if supplier is None:
		raise HTTPException(status_code=404, detail=f"supplier {id} not found")
	return supplier


@router.put(path="/northwind/suppliers/{id}", tags=["supplier"], status_code=status.HTTP_200_OK)
async def update_supplier(id: int, data: Dict = Body):
	supplier = handler.get_by_id(id)
	if supplier is None:
		raise HTTPException(status_code=404, detail=f"supplier {id} not found")
	merged = supplier
	if isinstance(merged, dict):
		merged.update(data)
	else:
		merged = merged.model_dump()
		merged.update(data)
	if handler.update(id, Supplier(**merged)):
		return JSONResponse(content={"supplier": data, "status": "UPDATED"}, status_code=status.HTTP_200_OK)


@router.delete(path="/northwind/suppliers/{id}", tags=["supplier"], status_code=status.HTTP_202_ACCEPTED)
async def delete_supplier(id: int):
	if handler.delete(id):
		return JSONResponse(content={"supplier": id, "status": "DELETED"}, status_code=status.HTTP_200_OK)
	else:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"supplier: {id} not found")


add_pagination(router)
