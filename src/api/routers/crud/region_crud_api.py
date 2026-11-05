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
from control.crud.region_crud_ctl import RegionCrudCTL
from domain.region import Region

disable_installed_extensions_check()

router = APIRouter()
handler = RegionCrudCTL()

# Reference fields that ?expand= can replace with the referenced documents
EXPANDABLE = ()
EXPAND_HELP = "Comma-separated reference fields to replace with the referenced documents: none"


@router.post(path="/northwind/regions", response_model=Region, response_model_by_alias=False, status_code=status.HTTP_201_CREATED)
async def create_region(data: Dict = Body):
	try:
		data["id"] = data.get("id", None)
		region = Region(**data)
		region = handler.create(region)
		return region
	except ValidationError as e:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"incorrect input data: {data}")
	except Exception as e:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"region: {data} already exists")


@router.get(path="/northwind/regions", response_model=LimitOffsetPage[Region], response_model_by_alias=False)
async def fetch_regions(q: List[str] = Query(None), keys: str = "*", expand: str = Query(None, description=EXPAND_HELP)):
	keys = "*" if keys == "*" else {key: 1 for key in keys.split(",")}
	query = None if q is None else QueryParser.transform_query_conditions(q, Region)
	expand = HttpTools.parse_expand(expand, EXPANDABLE)
	regions = list(handler.fetch(query=query, keys=keys, expand=expand, reify=True if keys == "*" else False))
	return paginate(regions) if keys == "*" else JSONResponse(content=jsonable_encoder(regions))


@router.get(path="/northwind/regions/{id}", tags=["region"], response_model=Region, response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def find_region(id: int, expand: str = Query(None, description=EXPAND_HELP)):
	region = handler.get_by_id(id, expand=HttpTools.parse_expand(expand, EXPANDABLE))
	if region is None:
		raise HTTPException(status_code=404, detail=f"region {id} not found")
	return region


@router.put(path="/northwind/regions/{id}", tags=["region"], status_code=status.HTTP_200_OK)
async def update_region(id: int, data: Dict = Body):
	region = handler.get_by_id(id)
	if region is None:
		raise HTTPException(status_code=404, detail=f"region {id} not found")
	merged = region
	if isinstance(merged, dict):
		merged.update(data)
	else:
		merged = merged.model_dump()
		merged.update(data)
	if handler.update(id, Region(**merged)):
		return JSONResponse(content={"region": data, "status": "UPDATED"}, status_code=status.HTTP_200_OK)


@router.delete(path="/northwind/regions/{id}", tags=["region"], status_code=status.HTTP_202_ACCEPTED)
async def delete_region(id: int):
	if handler.delete(id):
		return JSONResponse(content={"region": id, "status": "DELETED"}, status_code=status.HTTP_200_OK)
	else:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"region: {id} not found")


add_pagination(router)
