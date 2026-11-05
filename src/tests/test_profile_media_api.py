"""Profile and media routes, with peerforce's role check (the 'user' role), on a throwaway database and local storage."""
import io
import uuid

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pymongo import MongoClient

from api import settings
from api.northwind_app import app
from data.generic_dao import GenericDAO
from domain.common.profile import Profile
from domain.common.media import Media
from domain.common.user_credentials import UserCredentials
from control.common.profile_manager_ctl import ProfileManagerCTL
from control.common.media_manager_ctl import MediaManagerCTL
from services.storage.impl.local_storage import LocalStorageService
from services.authorization.authorization_handler import AuthorizationHandler

client = TestClient(app)

UNKNOWN_MEDIA = "/northwind/media/" + "0" * 24


@pytest.fixture
def dao(monkeypatch, tmp_path):
    """Profiles and media live in a throwaway database; uploads land in a temporary local volume."""
    dbname = f"{settings.DBNAME}_test_media_{uuid.uuid4().hex[:8]}"
    dao = GenericDAO(dbname=dbname)
    storage = LocalStorageService()
    storage.base_path = str(tmp_path / "volumes")
    monkeypatch.setattr(ProfileManagerCTL, "dao", dao)
    monkeypatch.setattr(MediaManagerCTL, "dao", dao)
    monkeypatch.setattr(MediaManagerCTL, "storage", storage)
    monkeypatch.setattr(settings, "LOCAL_STORAGE_PATH", str(tmp_path / "uploads"))
    yield dao
    MongoClient(settings.MONGO_SERVER).drop_database(dbname)


def bearer(profile_id, roles):
    credentials = UserCredentials(id=profile_id, name="Member", email=f"member.{profile_id[:8]}@northwind.test", roles=list(roles))
    return {"Authorization": f"Bearer {AuthorizationHandler().encode_token(credentials)}"}


def member(dao, roles=("user",)):
    """A stored profile, and the bearer header of a session for it."""
    profile_id = uuid.uuid4().hex[:24]
    dao.insert(entity=Profile, data=Profile(id=profile_id, name="Member", email=f"member.{profile_id[:8]}@northwind.test", roles=list(roles)))
    return profile_id, bearer(profile_id, roles)


def png(width, height):
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (200, 30, 30)).save(buffer, format="PNG")
    return buffer.getvalue()


def stored_image(media):
    return Image.open(MediaManagerCTL.storage.get_file_url(volume=settings.STORAGE_VOLUME, file_path=media.oid))


def test_profile_returns_the_callers_profile(dao):
    profile_id, headers = member(dao)

    response = client.get("/northwind/profile", headers=headers)

    assert response.status_code == 200
    assert response.json()["id"] == profile_id


def test_profile_needs_the_user_role(dao):
    _, headers = member(dao, roles=["super"])

    assert client.get("/northwind/profile", headers=headers).status_code == 403


def test_profile_without_a_stored_profile_is_not_found(dao):
    assert client.get("/northwind/profile", headers=bearer("0" * 24, ["user"])).status_code == 404


def test_profile_patch_updates_the_callers_fields(dao):
    profile_id, headers = member(dao)

    response = client.patch("/northwind/profile", headers=headers, json={"name": "Nancy Davolio", "phone": "(206) 555-9857"})

    stored = dao.find_by_id(entity=Profile, id=profile_id)
    assert response.status_code == 200
    assert (stored.name, stored.phone) == ("Nancy Davolio", "(206) 555-9857")


def test_profile_patch_keeps_the_avatar(dao):
    profile_id, headers = member(dao)
    client.patch("/northwind/profile/avatar", headers=headers, files={"file": ("me.png", png(64, 64), "image/png")})

    response = client.patch("/northwind/profile", headers=headers, json={"name": "Nancy Davolio"})

    assert response.status_code == 200
    assert response.json()["avatar"]["owner"] == profile_id


def test_profile_patch_stores_no_duplicate_bookkeeping_fields(dao):
    profile_id, headers = member(dao)

    client.patch("/northwind/profile", headers=headers, json={"name": "Nancy Davolio"})

    document = MongoClient(settings.MONGO_SERVER)[dao.dbname]["profiles"].find_one({"_id": profile_id})
    assert {"id", "version", "created", "updated"}.isdisjoint(document)
    assert document["_version"] == 2


def test_profile_patch_cannot_change_the_email(dao):
    profile_id, headers = member(dao)
    email = dao.find_by_id(entity=Profile, id=profile_id).email

    response = client.patch("/northwind/profile", headers=headers, json={"email": "other@northwind.test"})

    assert response.status_code == 400
    assert dao.find_by_id(entity=Profile, id=profile_id).email == email


def test_profile_patch_cannot_grant_roles(dao):
    profile_id, headers = member(dao)

    client.patch("/northwind/profile", headers=headers, json={"name": "Nancy", "roles": ["super"]})

    assert dao.find_by_id(entity=Profile, id=profile_id).roles == ["user"]


def test_avatar_upload_stores_a_thumbnail_and_links_it(dao, monkeypatch):
    monkeypatch.setattr(settings, "THUMBNAIL_MAX_BBOX", 400)
    profile_id, headers = member(dao)

    response = client.patch("/northwind/profile/avatar", headers=headers, files={"file": ("me.png", png(1600, 1200), "image/png")})

    media = dao.find_by_id(entity=Media, id=response.json()["avatar"])
    assert response.status_code == 201
    assert dao.find_by_id(entity=Profile, id=profile_id).avatar == media.id
    assert stored_image(media).size == (400, 300)


def test_profile_shows_the_avatar_with_a_url(dao):
    profile_id, headers = member(dao)
    client.patch("/northwind/profile/avatar", headers=headers, files={"file": ("me.png", png(64, 64), "image/png")})

    avatar = client.get("/northwind/profile", headers=headers).json()["avatar"]

    assert avatar["owner"] == profile_id
    assert Image.open(avatar["url"]).size == (64, 64)


def test_avatar_upload_rejects_files_that_are_not_media(dao):
    _, headers = member(dao)

    response = client.patch("/northwind/profile/avatar", headers=headers, files={"file": ("run.exe", b"MZ", "application/x-msdownload")})

    assert response.status_code == 422
    assert response.json() == {"state": "UNSUPPORTED_MEDIA_FORMAT"}


def test_media_upload_stores_the_file_for_its_owner(dao):
    profile_id, headers = member(dao)

    response = client.post(f"/northwind/media/user/{profile_id}/products", headers=headers, files={"file": ("chai.png", png(32, 32), "image/png")})

    media = dao.find_by_id(entity=Media, id=response.json()["id"])
    assert response.status_code == 201
    assert media.owner == profile_id
    assert stored_image(media).size == (32, 32)


def test_media_url_is_issued_for_a_stored_file(dao):
    profile_id, headers = member(dao)
    upload = client.post(f"/northwind/media/user/{profile_id}/products", headers=headers, files={"file": ("chai.png", png(32, 32), "image/png")})

    response = client.get(f"/northwind/media/{upload.json()['id']}", headers=headers)

    assert response.status_code == 200
    assert Image.open(response.json()["url"]).size == (32, 32)


def test_unknown_media_is_not_found(dao):
    _, headers = member(dao)

    assert client.get(UNKNOWN_MEDIA, headers=headers).status_code == 404


def test_media_needs_the_user_role(dao):
    profile_id, headers = member(dao, roles=["super"])

    assert client.post(f"/northwind/media/user/{profile_id}/products", headers=headers, files={"file": ("chai.png", png(8, 8), "image/png")}).status_code == 403
    assert client.get(UNKNOWN_MEDIA, headers=headers).status_code == 403


def test_profile_and_media_need_a_session(dao):
    assert client.get("/northwind/profile").status_code == 401
    assert client.get(UNKNOWN_MEDIA).status_code == 401
