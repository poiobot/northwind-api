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
from control.crud.product_crud_ctl import ProductCrudCTL
from domain.product import Product

disable_installed_extensions_check()

router = APIRouter()
handler = ProductCrudCTL()

# Reference fields that ?expand= can replace with the referenced documents
EXPANDABLE = ("SupplierID", "CategoryID",)
EXPAND_HELP = "Comma-separated reference fields to replace with the referenced documents: SupplierID, CategoryID"


@router.post(path="/northwind/products", response_model=Product, response_model_by_alias=False, status_code=status.HTTP_201_CREATED)
async def create_product(data: Dict = Body):
	try:
		data["id"] = data.get("id", None)
		product = Product(**data)
		product = handler.create(product)
		return product
	except ValidationError as e:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"incorrect input data: {data}")
	except Exception as e:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"product: {data} already exists")


@router.get(path="/northwind/products", response_model=LimitOffsetPage[Product], response_model_by_alias=False)
async def fetch_products(q: List[str] = Query(None), keys: str = "*", expand: str = Query(None, description=EXPAND_HELP)):
	keys = "*" if keys == "*" else {key: 1 for key in keys.split(",")}
	query = None if q is None else QueryParser.transform_query_conditions(q, Product)
	expand = HttpTools.parse_expand(expand, EXPANDABLE)
	products = list(handler.fetch(query=query, keys=keys, expand=expand, reify=True if keys == "*" else False))
	return paginate(products) if keys == "*" else JSONResponse(content=jsonable_encoder(products))


@router.get(path="/northwind/products/{id}", tags=["product"], response_model=Product, response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def find_product(id: int, expand: str = Query(None, description=EXPAND_HELP)):
	product = handler.get_by_id(id, expand=HttpTools.parse_expand(expand, EXPANDABLE))
	if product is None:
		raise HTTPException(status_code=404, detail=f"product {id} not found")
	return product


@router.put(path="/northwind/products/{id}", tags=["product"], status_code=status.HTTP_200_OK)
async def update_product(id: int, data: Dict = Body):
	product = handler.get_by_id(id)
	if product is None:
		raise HTTPException(status_code=404, detail=f"product {id} not found")
	merged = product
	if isinstance(merged, dict):
		merged.update(data)
	else:
		merged = merged.model_dump()
		merged.update(data)
	if handler.update(id, Product(**merged)):
		return JSONResponse(content={"product": data, "status": "UPDATED"}, status_code=status.HTTP_200_OK)


@router.delete(path="/northwind/products/{id}", tags=["product"], status_code=status.HTTP_202_ACCEPTED)
async def delete_product(id: int):
	if handler.delete(id):
		return JSONResponse(content={"product": id, "status": "DELETED"}, status_code=status.HTTP_200_OK)
	else:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"product: {id} not found")


add_pagination(router)
