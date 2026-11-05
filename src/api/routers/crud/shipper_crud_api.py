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
from control.crud.shipper_crud_ctl import ShipperCrudCTL
from domain.shipper import Shipper

disable_installed_extensions_check()

router = APIRouter()
handler = ShipperCrudCTL()

# Reference fields that ?expand= can replace with the referenced documents
EXPANDABLE = ()
EXPAND_HELP = "Comma-separated reference fields to replace with the referenced documents: none"


@router.post(path="/northwind/shippers", response_model=Shipper, response_model_by_alias=False, status_code=status.HTTP_201_CREATED)
async def create_shipper(data: Dict = Body):
	try:
		data["id"] = data.get("id", None)
		shipper = Shipper(**data)
		shipper = handler.create(shipper)
		return shipper
	except ValidationError as e:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"incorrect input data: {data}")
	except Exception as e:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"shipper: {data} already exists")


@router.get(path="/northwind/shippers", response_model=LimitOffsetPage[Shipper], response_model_by_alias=False)
async def fetch_shippers(q: List[str] = Query(None), keys: str = "*", expand: str = Query(None, description=EXPAND_HELP)):
	keys = "*" if keys == "*" else {key: 1 for key in keys.split(",")}
	query = None if q is None else QueryParser.transform_query_conditions(q, Shipper)
	expand = HttpTools.parse_expand(expand, EXPANDABLE)
	shippers = list(handler.fetch(query=query, keys=keys, expand=expand, reify=True if keys == "*" else False))
	return paginate(shippers) if keys == "*" else JSONResponse(content=jsonable_encoder(shippers))


@router.get(path="/northwind/shippers/{id}", tags=["shipper"], response_model=Shipper, response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def find_shipper(id: int, expand: str = Query(None, description=EXPAND_HELP)):
	shipper = handler.get_by_id(id, expand=HttpTools.parse_expand(expand, EXPANDABLE))
	if shipper is None:
		raise HTTPException(status_code=404, detail=f"shipper {id} not found")
	return shipper


@router.put(path="/northwind/shippers/{id}", tags=["shipper"], status_code=status.HTTP_200_OK)
async def update_shipper(id: int, data: Dict = Body):
	shipper = handler.get_by_id(id)
	if shipper is None:
		raise HTTPException(status_code=404, detail=f"shipper {id} not found")
	merged = shipper
	if isinstance(merged, dict):
		merged.update(data)
	else:
		merged = merged.model_dump()
		merged.update(data)
	if handler.update(id, Shipper(**merged)):
		return JSONResponse(content={"shipper": data, "status": "UPDATED"}, status_code=status.HTTP_200_OK)


@router.delete(path="/northwind/shippers/{id}", tags=["shipper"], status_code=status.HTTP_202_ACCEPTED)
async def delete_shipper(id: int):
	if handler.delete(id):
		return JSONResponse(content={"shipper": id, "status": "DELETED"}, status_code=status.HTTP_200_OK)
	else:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"shipper: {id} not found")


add_pagination(router)
