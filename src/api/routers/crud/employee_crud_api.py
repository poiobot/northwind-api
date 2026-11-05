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
from control.crud.employee_crud_ctl import EmployeeCrudCTL
from domain.employee import Employee

disable_installed_extensions_check()

router = APIRouter()
handler = EmployeeCrudCTL()

# Reference fields that ?expand= can replace with the referenced documents
EXPANDABLE = ()
EXPAND_HELP = "Comma-separated reference fields to replace with the referenced documents: none"


@router.post(path="/northwind/employees", response_model=Employee, response_model_by_alias=False, status_code=status.HTTP_201_CREATED)
async def create_employee(data: Dict = Body):
	try:
		data["id"] = data.get("id", None)
		employee = Employee(**data)
		employee = handler.create(employee)
		return employee
	except ValidationError as e:
		raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"incorrect input data: {data}")
	except Exception as e:
		raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"employee: {data} already exists")


@router.get(path="/northwind/employees", response_model=LimitOffsetPage[Employee], response_model_by_alias=False)
async def fetch_employees(q: List[str] = Query(None), keys: str = "*", expand: str = Query(None, description=EXPAND_HELP)):
	keys = "*" if keys == "*" else {key: 1 for key in keys.split(",")}
	query = None if q is None else QueryParser.transform_query_conditions(q, Employee)
	expand = HttpTools.parse_expand(expand, EXPANDABLE)
	employees = list(handler.fetch(query=query, keys=keys, expand=expand, reify=True if keys == "*" else False))
	return paginate(employees) if keys == "*" else JSONResponse(content=jsonable_encoder(employees))


@router.get(path="/northwind/employees/{id}", tags=["employee"], response_model=Employee, response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def find_employee(id: int, expand: str = Query(None, description=EXPAND_HELP)):
	employee = handler.get_by_id(id, expand=HttpTools.parse_expand(expand, EXPANDABLE))
	if employee is None:
		raise HTTPException(status_code=404, detail=f"employee {id} not found")
	return employee


@router.put(path="/northwind/employees/{id}", tags=["employee"], status_code=status.HTTP_200_OK)
async def update_employee(id: int, data: Dict = Body):
	employee = handler.get_by_id(id)
	if employee is None:
		raise HTTPException(status_code=404, detail=f"employee {id} not found")
	merged = employee
	if isinstance(merged, dict):
		merged.update(data)
	else:
		merged = merged.model_dump()
		merged.update(data)
	if handler.update(id, Employee(**merged)):
		return JSONResponse(content={"employee": data, "status": "UPDATED"}, status_code=status.HTTP_200_OK)


@router.delete(path="/northwind/employees/{id}", tags=["employee"], status_code=status.HTTP_202_ACCEPTED)
async def delete_employee(id: int):
	if handler.delete(id):
		return JSONResponse(content={"employee": id, "status": "DELETED"}, status_code=status.HTTP_200_OK)
	else:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"employee: {id} not found")


add_pagination(router)
