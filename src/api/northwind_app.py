from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware

import domain.model  # noqa: F401 — resolve forward references before router imports
from routers.crud import region_crud_api, shipper_crud_api, product_crud_api, category_crud_api, employee_crud_api, customer_crud_api, supplier_crud_api, order_crud_api, order_detail_crud_api, employee_territory_crud_api
from routers.common import authentication_manager_api, profile_manager_api, media_manager_api
from api.service_descriptor import router as describe_router
from api import settings
from lib.representation import install_representations
from domain.common.user_credentials import UserCredentials
from services.authorization.authorization_handler import AuthorizationHandler
app = FastAPI()

authorisation_handler = AuthorizationHandler()

# Roles on the generated CRUD routes, checked when they are mounted so the generated routers stay
# untouched: any known role reads, admins write
read_roles_check = authorisation_handler.require_roles(["user", "admin", "super"])
write_roles_check = authorisation_handler.require_roles(["admin", "super"])


def crud_roles_check(request: Request, credentials: UserCredentials = Depends(authorisation_handler.verify_token_dependency)) -> UserCredentials:
	if request.method in ("GET", "HEAD"):
		return read_roles_check(credentials)
	return write_roles_check(credentials)


crud_access = [Depends(crud_roles_check)]

install_representations(app)

origins = settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS else ["*"]
app.add_middleware(
	CORSMiddleware,
	allow_origins=origins,
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"]
)

app.include_router(region_crud_api.router, dependencies=crud_access)
app.include_router(shipper_crud_api.router, dependencies=crud_access)
app.include_router(product_crud_api.router, dependencies=crud_access)
app.include_router(category_crud_api.router, dependencies=crud_access)
app.include_router(employee_crud_api.router, dependencies=crud_access)
app.include_router(customer_crud_api.router, dependencies=crud_access)
app.include_router(supplier_crud_api.router, dependencies=crud_access)
app.include_router(order_crud_api.router, dependencies=crud_access)
app.include_router(order_detail_crud_api.router, dependencies=crud_access)
app.include_router(employee_territory_crud_api.router, dependencies=crud_access)
app.include_router(authentication_manager_api.router)
app.include_router(profile_manager_api.router)
app.include_router(media_manager_api.router)
app.include_router(describe_router)

try:
	import hooks_config
except ImportError:
	pass


if __name__ == "__main__":
	import uvicorn
	uvicorn.run(app, host="0.0.0.0", port=2112)
