from domain.common.user import User
from domain.common.user_credentials import UserCredentials
from control.common.authentication_manager_ctl import AuthenticationManagerCTL
from services.authorization.authorization_handler import AuthorizationHandler as AuthorisationHandler

from fastapi import APIRouter, Depends, Body, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from fastapi_pagination.utils import disable_installed_extensions_check
from typing import Dict
from datetime import datetime

import logging

from api import settings

disable_installed_extensions_check()

router = APIRouter(prefix=f"/{settings.PROJECT_NAME}/auth", tags=["Authentication API"])

authorisation_handler = AuthorisationHandler()


@router.post(path="/users", status_code=status.HTTP_201_CREATED)
async def register_new_user(user_form: User):
    state, uid = AuthenticationManagerCTL.register(user=user_form)
    if state in ["USER_ALREADY_REGISTERED", "INVALID_EMAIL_FORMAT", "WEAK_PASSWORD"]:
        return JSONResponse(content={"state": state, "email": user_form.email}, status_code=status.HTTP_200_OK)
    return JSONResponse(content={"state": state, "user_id": uid}, status_code=status.HTTP_201_CREATED)

@router.post(path="/users/role/{role}")
async def preregister_users(role: str, request: Request, users: dict=Body, credentials: UserCredentials = Depends(authorisation_handler.require_roles(["admin", "super"]))):
    if role in ["admin", "super"]:
        return JSONResponse(content={"state": "ADMINS_REGISTRATION_NOT_ALLOWED"})
    args = {k:v for k,v in request.query_params.items()}
    users_ids = list()
    for data in users.get("users", []):
        try:
            user = User(**data)
            data.pop("name", None)
            data.pop("email", None)
            payload = data | args
            code, profile_id = AuthenticationManagerCTL.preregister(user=user, roles=[role], **payload)
            users_ids.append(profile_id)
        except Exception as e:
            logging.info(msg=f"UNKNOWN_USER_DATA_FORMAT: {data}")
            continue
    return JSONResponse(content={"state": "USERS_PREREGISTERED", "users_ids": users_ids}, status_code=status.HTTP_201_CREATED)

@router.patch(path="/user/{user_id}")
async def activate_user(user_id: str, form_data: Dict = Body):
    code = AuthenticationManagerCTL.activate(user_id=user_id, code=form_data["code"])
    if code == "USER_NOT_FOUND":
        return JSONResponse(content={"state": code}, status_code=status.HTTP_404_NOT_FOUND)
    if code == "REGISTER_AGAIN":
        return JSONResponse(content={"state": "TOO_MANY_REQUEST", "action": "REGISTER_AGAIN"},
                            status_code=status.HTTP_429_TOO_MANY_REQUESTS)
    if code == "INVALID_CODE":
        return JSONResponse(content={"state": code, "action": "SEND_VALID_CODE"},
                            status_code=status.HTTP_401_UNAUTHORIZED)
    return JSONResponse(content={"state": code, "action": "LOGIN"}, status_code=status.HTTP_202_ACCEPTED)

@router.post(path="/sessions", response_model_by_alias=False, status_code=status.HTTP_201_CREATED)
async def login(login_form: Dict = Body):
    # TODO review oauth2 authentication JNA
    state, profile, jwt = AuthenticationManagerCTL.login(**login_form)
    if not jwt:
        return JSONResponse(
            content={"state": state} | {"timestamp": str(datetime.now())},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    status_code = status.HTTP_200_OK
    if state == "USER_CREATED":
        status_code = status.HTTP_201_CREATED
    return JSONResponse(
        content={"state": state, "profile": jsonable_encoder(profile, by_alias=False), "session_token": jwt} | {"timestamp": str(datetime.now())}, status_code=status_code)

@router.post(path="/admin/sessions", response_model_by_alias=False, status_code=status.HTTP_201_CREATED)
async def admin_login(login_form: Dict = Body):
    state, profile, jwt = AuthenticationManagerCTL.login(
        email=login_form.get("email", ""),
        password=login_form.get("password", ""),
        token=login_form.get("token", None)
    )
    if jwt is None:
        return JSONResponse(content={"state": state} | {"timestamp": str(datetime.now())},status_code=status.HTTP_401_UNAUTHORIZED,)

    # TODO: Check admin role from table, not from profile
    if not {"super", "admin"}.intersection(set(profile.roles)):
        return JSONResponse(content={"state": "INVALID_CREDENTIALS"}, status_code=status.HTTP_401_UNAUTHORIZED)

    status_code = status.HTTP_200_OK
    if state == "USER_CREATED":
        status_code = status.HTTP_201_CREATED
    return JSONResponse(
        content={"state": state, "profile": jsonable_encoder(profile, by_alias=False), "session_token": jwt} | {
            "timestamp": str(datetime.now())}, status_code=status_code)

@router.post(path="/email/{email}/codes")
async def request_email_validation_code(email: str):
    state = AuthenticationManagerCTL.send_email_validation_code(email=email)
    if state == "EMAIL_NOT_FOUND":
        return JSONResponse(content={"state": state}, status_code=status.HTTP_404_NOT_FOUND)
    return JSONResponse(content={"state": state, "action": "INTRODUCE_CODE"}, status_code=status.HTTP_202_ACCEPTED)

@router.patch(path="/email/{email}/code")
async def match_email_validation_code(email: str, data: Dict = Body):
    code = data.get("code", None)
    if not code:
        return JSONResponse(content={"state": "EXPECTING_CODE"}, status_code=status.HTTP_401_UNAUTHORIZED)
    state, token = AuthenticationManagerCTL.match_email_validation_code(email=email, code=code)
    if state != "VALID_CODE":
        return JSONResponse(content={"state": state}, status_code=status.HTTP_401_UNAUTHORIZED)
    return JSONResponse(content={"state": state, "token": token}, status_code=status.HTTP_202_ACCEPTED)

@router.put(path="/password")
async def reset_password(data: Dict = Body):
    token = data.get("token", None)
    password = data.get("password", None)
    if not password or not token:
        return JSONResponse(content={"state": "INVALID_REQUEST"}, status_code=status.HTTP_400_BAD_REQUEST)
    state = AuthenticationManagerCTL.reset_password(token=token, password=password)
    if state == "USER_NOT_FOUND":
        return JSONResponse(content={"state": state}, status_code=status.HTTP_404_NOT_FOUND)
    if state == "EXPIRED_TOKEN":
        return JSONResponse(content={"state": state}, status_code=status.HTTP_408_REQUEST_TIMEOUT)
    if state != "PASSWORD_RESET":
        return JSONResponse(content={"state": state}, status_code=status.HTTP_400_BAD_REQUEST)
    return JSONResponse(content={"state": state, "action": "LOGIN"}, status_code=status.HTTP_202_ACCEPTED)


