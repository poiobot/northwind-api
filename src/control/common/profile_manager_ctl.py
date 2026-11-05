from domain.model import Profile, Media
from data.generic_dao import GenericDAO
from control.common.media_manager_ctl import MediaManagerCTL

from fastapi import UploadFile
from io import BytesIO
from typing import List, Dict, Tuple, Union
from datetime import datetime, timezone
import logging

from api import settings


class ProfileManagerCTL:

    dao = GenericDAO()
    media_handler = MediaManagerCTL()

    @classmethod
    def get_user_profile(cls, profile_id: str) -> Tuple[str, Profile or None]:
        """
        Returns a list of available lessons with a specific level and in the date's month
        :param profile_id: id of player
        :return: A tuple containing a status code, and the player profile
        """
        profile = cls.dao.find_by_id(entity=Profile, id=profile_id, expand=["properties", "avatar"])
        if not profile:
            return "USER_PROFILE_NOT_FOUND", None
        # Get a fresh presigned URL for user avatar
        if profile.avatar:
            _, profile.avatar = cls.media_handler.get_url(profile.avatar)
        return "USER_PROFILE", profile

    @classmethod
    def update_user_profile(cls, profile_id: str, changes: Profile) -> Tuple[str, Profile or None]:
        """
        Updates personal details of a user. ID and email cannot be updated from this endpoint.
        TODO: Implement endpoint PUT /padmi/user/{user_id}/email to change user email
        :param profile_id: A profile object containing the updated details
        :param data: A dict containing the updated details
        :return: a Profile object containing the updated details
        """
        try:
            profile = cls.dao.find_by_id(entity=Profile, id=profile_id)
            if not profile:
                return "USER_PROFILE_NOT_FOUND", None
            changes = changes.model_dump(by_alias=False)
            keys = [key for key in changes.keys() if changes[key] and key != "roles"]
            if not keys or set(keys).intersection({ "id", "email"}):
                return "INVALID_USER_PROFILE_CHANGE", None
            _profile = profile.model_dump(by_alias=True)
            for key in keys:
                _profile[key] = changes[key]
            profile = cls.dao.update(entity=Profile, id=profile_id, data=_profile)
            # Get a fresh presigned URL for user avatar
            if profile.avatar:
                _, profile.avatar = cls.media_handler.get_url(profile.avatar)
        except Exception as e:
            logging.warning(msg=f"Couldn't update user profile: {profile_id} - {e}")
            return "COULD_NOT_UPDATE_USER_PROFILE", None
        return "USER_PROFILE", profile

    @classmethod
    def patch_user_profile(cls, profile_id: str, changes: Dict) -> Tuple[str, Profile or None]:
        """
        Gets a dict of changes to update a user profile.
        :param profile_id:
        :param changes:
        :return:
        """
        try:
            profile = cls.dao.find_by_id(entity=Profile, id=profile_id)
            if not profile:
                return "USER_PROFILE_NOT_FOUND", None
            keys = [key for key in changes.keys() if changes[key] and key != "roles"]
            if not keys or set(keys).intersection({"id", "email"}):
                return "INVALID_USER_PROFILE_CHANGE", None
            _profile = profile.model_dump(by_alias=True)
            for key in keys:
                _profile[key] = changes[key]
            profile = cls.dao.update(entity=Profile, id=profile_id, data=_profile)
            # Get a fresh presigned URL for user avatar
            if profile.avatar:
                _, profile.avatar = cls.media_handler.get_url(profile.avatar)

        except Exception as e:
            logging.warning(msg=f"Couldn't update user profile: {profile_id} - {e}")
            return "COULD_NOT_UPDATE_USER_PROFILE", None
        return "USER_PROFILE", profile

    @classmethod
    def upload_avatar(cls, profile_id: str, file: Union[UploadFile, BytesIO]) -> Tuple[str, Profile or str]:
        profile = cls.dao.find_by_id(entity=Profile, id=profile_id)
        if not profile:
            return "USER_PROFILE_NOT_FOUND", profile_id
        state, media = cls.media_handler.upload(user_id=profile_id, parent_dir="avatar", file=file, max_image_size=settings.THUMBNAIL_MAX_BBOX)
        if state == "UNSUPPORTED_MEDIA_FORMAT":
            return state, None
        profile.avatar = media.id
        profile = cls.dao.update(entity=Profile, id=profile_id, data=profile)
        logging.info(msg=f"{datetime.now(timezone.utc)}: Uploaded profile avatar {media.id}")
        return "USER_AVATAR_UPLOADED", profile

