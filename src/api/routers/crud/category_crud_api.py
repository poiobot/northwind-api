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
from control.crud.category_crud_ctl import CategoryCrudCTL
from domain.category import Category

disable_installed_extensions_check()

router = APIRouter()
handler = CategoryCrudCTL()

# Reference fields that ?expand= can replace with the referenced documents
EXPANDABLE = ()
EXPAND_HELP = "Comma-separated reference fields to replace with the referenced documents: none"


@router.post(path="/northwind/categories", response_model=Category, response_model_by_alias=False, status_code=status.HTTP_201_CREATED)
async def create_category(data: Dict = Body):
	try:
		data["id"] = data.get("id", None)
		category = Category(**data)
		category = handler.create(category)
		return category
	except ValidationError as e:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"incorrect input data: {data}")
	except Exception as e:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"category: {data} already exists")


@router.get(path="/northwind/categories", response_model=LimitOffsetPage[Category], response_model_by_alias=False)
async def fetch_categories(q: List[str] = Query(None), keys: str = "*", expand: str = Query(None, description=EXPAND_HELP)):
	keys = "*" if keys == "*" else {key: 1 for key in keys.split(",")}
	query = None if q is None else QueryParser.transform_query_conditions(q, Category)
	expand = HttpTools.parse_expand(expand, EXPANDABLE)
	categories = list(handler.fetch(query=query, keys=keys, expand=expand, reify=True if keys == "*" else False))
	return paginate(categories) if keys == "*" else JSONResponse(content=jsonable_encoder(categories))


@router.get(path="/northwind/categories/{id}", tags=["category"], response_model=Category, response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def find_category(id: int, expand: str = Query(None, description=EXPAND_HELP)):
	category = handler.get_by_id(id, expand=HttpTools.parse_expand(expand, EXPANDABLE))
	if category is None:
		raise HTTPException(status_code=404, detail=f"category {id} not found")
	return category


@router.put(path="/northwind/categories/{id}", tags=["category"], status_code=status.HTTP_200_OK)
async def update_category(id: int, data: Dict = Body):
	category = handler.get_by_id(id)
	if category is None:
		raise HTTPException(status_code=404, detail=f"category {id} not found")
	merged = category
	if isinstance(merged, dict):
		merged.update(data)
	else:
		merged = merged.model_dump()
		merged.update(data)
	if handler.update(id, Category(**merged)):
		return JSONResponse(content={"category": data, "status": "UPDATED"}, status_code=status.HTTP_200_OK)


@router.delete(path="/northwind/categories/{id}", tags=["category"], status_code=status.HTTP_202_ACCEPTED)
async def delete_category(id: int):
	if handler.delete(id):
		return JSONResponse(content={"category": id, "status": "DELETED"}, status_code=status.HTTP_200_OK)
	else:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"category: {id} not found")


add_pagination(router)
