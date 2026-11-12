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
from control.crud.employee_territory_crud_ctl import EmployeeTerritoryCrudCTL
from domain.employee_territory import EmployeeTerritory

disable_installed_extensions_check()

router = APIRouter()
handler = EmployeeTerritoryCrudCTL()

# Reference fields that ?expand= can replace with the referenced documents
EXPANDABLE = ("EmployeeID", "TerritoryID",)
EXPAND_HELP = "Comma-separated reference fields to replace with the referenced documents: EmployeeID, TerritoryID"


@router.post(path="/northwind/employee_territories", response_model=EmployeeTerritory, response_model_by_alias=False, status_code=status.HTTP_201_CREATED)
async def create_employee_territory(data: Dict = Body):
	try:
		data["id"] = data.get("id", None)
		employee_territory = EmployeeTerritory(**data)
		employee_territory = handler.create(employee_territory)
		return employee_territory
	except ValidationError as e:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"incorrect input data: {data}")
	except Exception as e:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"employee_territory: {data} already exists")


@router.get(path="/northwind/employee_territories", response_model=LimitOffsetPage[EmployeeTerritory], response_model_by_alias=False)
async def fetch_employee_territories(q: List[str] = Query(None), keys: str = "*", expand: str = Query(None, description=EXPAND_HELP)):
	keys = "*" if keys == "*" else {key: 1 for key in keys.split(",")}
	query = None if q is None else QueryParser.transform_query_conditions(q, EmployeeTerritory)
	expand = HttpTools.parse_expand(expand, EXPANDABLE)
	employee_territories = list(handler.fetch(query=query, keys=keys, expand=expand, reify=True if keys == "*" else False))
	return paginate(employee_territories) if keys == "*" else JSONResponse(content=jsonable_encoder(employee_territories))


@router.get(path="/northwind/employee_territories/{id}", tags=["employee_territory"], response_model=EmployeeTerritory, response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def find_employee_territory(id: int, expand: str = Query(None, description=EXPAND_HELP)):
	employee_territory = handler.get_by_id(id, expand=HttpTools.parse_expand(expand, EXPANDABLE))
	if employee_territory is None:
		raise HTTPException(status_code=404, detail=f"employee_territory {id} not found")
	return employee_territory


@router.put(path="/northwind/employee_territories/{id}", tags=["employee_territory"], status_code=status.HTTP_200_OK)
async def update_employee_territory(id: int, data: Dict = Body):
	employee_territory = handler.get_by_id(id)
	if employee_territory is None:
		raise HTTPException(status_code=404, detail=f"employee_territory {id} not found")
	merged = employee_territory
	if isinstance(merged, dict):
		merged.update(data)
	else:
		merged = merged.model_dump()
		merged.update(data)
	if handler.update(id, EmployeeTerritory(**merged)):
		return JSONResponse(content={"employee_territory": data, "status": "UPDATED"}, status_code=status.HTTP_200_OK)


@router.delete(path="/northwind/employee_territories/{id}", tags=["employee_territory"], status_code=status.HTTP_202_ACCEPTED)
async def delete_employee_territory(id: int):
	if handler.delete(id):
		return JSONResponse(content={"employee_territory": id, "status": "DELETED"}, status_code=status.HTTP_200_OK)
	else:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"employee_territory: {id} not found")


add_pagination(router)
