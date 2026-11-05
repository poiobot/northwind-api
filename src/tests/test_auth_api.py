"""Role checks on the mounted API: the generated CRUD routes and the authentication routes.

Requests here never write: reads, refusals, and a malformed body that the route rejects once past the role check.
"""
import pytest
from fastapi.testclient import TestClient

from api.northwind_app import app
from domain.common.user_credentials import UserCredentials
from services.authorization.authorization_handler import AuthorizationHandler

client = TestClient(app)

MALFORMED_REGION = {"regionDescription": {"not": "text"}}
MISSING_REGION = "/northwind/regions/999999"


def bearer(*roles):
    credentials = UserCredentials(id="0" * 24, name="Tester", email="tester@northwind.test", roles=list(roles))
    return {"Authorization": f"Bearer {AuthorizationHandler().encode_token(credentials)}"}


def test_crud_read_without_token_is_unauthorized():
    assert client.get("/northwind/regions").status_code == 401


def test_crud_read_with_a_forged_token_is_unauthorized():
    assert client.get("/northwind/regions", headers={"Authorization": "Bearer not-a-token"}).status_code == 401


@pytest.mark.parametrize("role", ["user", "admin", "super"])
def test_crud_read_is_allowed_to_known_roles(role):
    assert client.get("/northwind/regions", headers=bearer(role)).status_code == 200
    assert client.get("/northwind/regions/1", headers=bearer(role)).status_code == 200


def test_crud_read_is_forbidden_without_a_known_role():
    assert client.get("/northwind/regions", headers=bearer("guest")).status_code == 403


@pytest.mark.parametrize("method, path", [("POST", "/northwind/regions"), ("PUT", MISSING_REGION), ("DELETE", MISSING_REGION)])
def test_crud_write_is_forbidden_to_plain_users(method, path):
    assert client.request(method, path, headers=bearer("user"), json=MALFORMED_REGION).status_code == 403


@pytest.mark.parametrize("role", ["admin", "super"])
def test_crud_write_passes_the_role_check_for_admins(role):
    assert client.post("/northwind/regions", headers=bearer(role), json=MALFORMED_REGION).status_code == 400
    assert client.delete(MISSING_REGION, headers=bearer(role)).status_code == 404


def test_login_route_refuses_unknown_credentials():
    response = client.post("/northwind/auth/sessions", json={"email": "nobody@northwind.test", "password": "Wr0ng!pass"})

    assert response.status_code == 401
    assert response.json()["state"] == "INVALID_CREDENTIALS"


def test_registration_with_a_weak_password_is_refused():
    response = client.post("/northwind/auth/users", json={"name": "Ann", "email": "ann@northwind.test", "password": "password"})

    assert response.status_code == 200
    assert response.json()["state"] == "WEAK_PASSWORD"


def test_password_reset_with_a_forged_token_is_refused():
    response = client.put("/northwind/auth/password", json={"token": "not-a-token", "password": "Northw1nd!pass"})

    assert response.status_code == 400
    assert response.json() == {"state": "INVALID_TOKEN"}


def test_preregistration_is_forbidden_to_plain_users():
    assert client.post("/northwind/auth/users/role/user", headers=bearer("user"), json={"users": []}).status_code == 403


def test_preregistration_is_open_to_admins():
    response = client.post("/northwind/auth/users/role/user", headers=bearer("admin"), json={"users": []})

    assert response.status_code == 201
    assert response.json() == {"state": "USERS_PREREGISTERED", "users_ids": []}
