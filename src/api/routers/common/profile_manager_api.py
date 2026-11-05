from domain.common.profile import Profile
from domain.common.user_credentials import UserCredentials
from control.common.profile_manager_ctl import ProfileManagerCTL
from services.authorization.authorization_handler import AuthorizationHandler as AuthorisationHandler

from fastapi import APIRouter, status, Body, Depends, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi_pagination import add_pagination
from fastapi_pagination.utils import disable_installed_extensions_check
from typing import Dict

from api import settings

disable_installed_extensions_check()

router = APIRouter(prefix=f"/{settings.PROJECT_NAME}", tags=["Profile Manager API"])

authorisation_handler = AuthorisationHandler()

message_codes = {
    "USER_PROFILE_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "COULD_NOT_UPDATE_USER_PROFILE": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "INVALID_USER_PROFILE_CHANGE": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "UNSUPPORTED_MEDIA_FORMAT": status.HTTP_422_UNPROCESSABLE_ENTITY,
}


@router.get(path="/profile", response_model=Profile, response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def get_user_profile(credentials: UserCredentials = Depends(authorisation_handler.require_roles(["user"]))):
    state, profile = ProfileManagerCTL.get_user_profile(profile_id=credentials.id)
    if state == "USER_PROFILE_NOT_FOUND":
        return JSONResponse(content={"state": state, "msg": f"User Profile for {credentials.id} not found"}, status_code=status.HTTP_404_NOT_FOUND)
    return profile

# @router.patch(path="/", response_model=Profile, response_model_by_alias=False, status_code=status.HTTP_200_OK)
# async def update_user_profile(changes: Profile, credentials: UserCredentials = Depends(authorisation_handler.require_roles(["user"]))):
#     state, profile = ProfileManagerCTL.update_user_profile(profile_id=credentials.id, changes=changes)
#     if state != "USER_PROFILE":
#         return JSONResponse(content={"state": state, "changes": jsonable_encoder(changes)}, status_code=status.HTTP_400_BAD_REQUEST)
#     return profile

@router.patch(path="/profile/avatar", response_model=Profile, response_model_by_alias=False, status_code=status.HTTP_201_CREATED)
async def upload_user_avatar(file: UploadFile = File(...), credentials: UserCredentials = Depends(authorisation_handler.require_roles(["user"]))):
    state, profile = ProfileManagerCTL.upload_avatar(profile_id=credentials.id, file=file)
    if state in ["USER_PROFILE_NOT_FOUND", "UNSUPPORTED_MEDIA_FORMAT"]:
        return JSONResponse(content={"state": state}, status_code=message_codes[state])
    return profile

@router.patch(path="/profile", response_model=Profile, response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def patch_user_profile(data: Dict = Body(), credentials : UserCredentials = Depends(authorisation_handler.require_roles(["user"]))):
    state, profile = ProfileManagerCTL.patch_user_profile(profile_id=credentials.id, changes=data)
    if state != "USER_PROFILE":
        return JSONResponse(content={"state": state, "data": data}, status_code=status.HTTP_400_BAD_REQUEST)
    return profile

add_pagination(router)
