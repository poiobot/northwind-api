from domain.common.media import Media
from domain.common.user_credentials import UserCredentials
from control.common.media_manager_ctl import MediaManagerCTL
from services.authorization.authorization_handler import AuthorizationHandler as AuthorisationHandler

from fastapi import APIRouter, status, Body, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi_pagination import add_pagination
from fastapi_pagination.utils import disable_installed_extensions_check

from api import settings

disable_installed_extensions_check()

router = APIRouter(prefix=f"/{settings.PROJECT_NAME}/media", tags=["Media Manager"])

authorisation_handler = AuthorisationHandler()

message_codes = {
    "USER_PROFILE_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "MEDIA_NOT_FOUND": status.HTTP_404_NOT_FOUND,
    "COULD_NOT_UPDATE_USER_PROFILE": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "INVALID_USER_PROFILE_CHANGE": status.HTTP_422_UNPROCESSABLE_ENTITY,
    "UNSUPPORTED_MEDIA_FORMAT": status.HTTP_422_UNPROCESSABLE_ENTITY,
}


@router.post(path="/user/{user_id}/{entity}", response_model=Media, response_model_by_alias=False, status_code=status.HTTP_201_CREATED)
async def upload_media(user_id: str, entity: str, file: UploadFile = File(...), credentials: UserCredentials = Depends(authorisation_handler.require_roles(["user"]))):
    state, media = MediaManagerCTL.upload(user_id=user_id, parent_dir=entity, file=file)
    if state in ["UNSUPPORTED_MEDIA_FORMAT"]:
        return JSONResponse(content={"state": state}, status_code=message_codes[state])
    return media

@router.get(path="/{media_id}", response_model=Media, response_model_by_alias=False, status_code=status.HTTP_200_OK)
async def get_media_url(media_id: str, credentials: UserCredentials = Depends(authorisation_handler.require_roles(["user"]))):
    state, media = MediaManagerCTL.get_url(media=media_id)
    if not media:
        return JSONResponse(content={"state": "MEDIA_NOT_FOUND"}, status_code=message_codes["MEDIA_NOT_FOUND"])
    return media

add_pagination(router)