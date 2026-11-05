"""AuthenticationManagerCTL: the authentication router's (state, ...) contract, served by services.authorization."""
import uuid

import pytest
from pymongo import MongoClient

from api import settings
from data.generic_dao import GenericDAO
from domain.common.user import User
from domain.common.profile import Profile
from control.common.authentication_manager_ctl import AuthenticationManagerCTL
from services.authorization.authorization_handler import AuthorizationHandler
from services.email.email_service import EmailService

PASSWORD = "Northw1nd!pass"
NEW_PASSWORD = "Northw1nd!changed"


@pytest.fixture
def dao(monkeypatch):
  """The controller works on a throwaway database and sends no email."""
  dbname = f"{settings.DBNAME}_test_auth_{uuid.uuid4().hex[:8]}"
  monkeypatch.setattr(AuthenticationManagerCTL, "dao", GenericDAO(dbname=dbname))
  monkeypatch.setattr(EmailService, "send_message", classmethod(lambda cls, **kwargs: None))
  yield AuthenticationManagerCTL.dao
  MongoClient(settings.MONGO_SERVER).drop_database(dbname)


def new_email():
  return f"tester.{uuid.uuid4().hex[:8]}@northwind.test"


def active_user(dao, roles=("user",)):
  """An activated user whose code is the cleared '----', like every user who has used theirs."""
  user_id, email = uuid.uuid4().hex[:24], new_email()
  password = AuthorizationHandler().get_password_hash(PASSWORD)
  dao.insert(entity=User, data=User(id=user_id, name="Tester", email=email, state="ACTIVE", password=password, profile=user_id))
  dao.insert(entity=Profile, data=Profile(id=user_id, name="Tester", email=email, roles=list(roles)))
  return user_id, email


def stored_code(dao, email):
  return list(dao.find_by_key_value(entity=User, key="email", value=email))[0].code


def test_login_returns_the_profile_and_a_token_carrying_its_roles(dao):
  user_id, email = active_user(dao, roles=["super"])

  state, profile, token = AuthenticationManagerCTL.login(email=email, password=PASSWORD)

  credentials = AuthorizationHandler().decode_token(token)
  assert state == "CONNECTED"
  assert profile.id == user_id
  assert (credentials.id, credentials.roles) == (user_id, ["super"])


def test_login_with_wrong_password_is_refused(dao):
  _, email = active_user(dao)

  assert AuthenticationManagerCTL.login(email=email, password="Wr0ng!pass") == ("INVALID_CREDENTIALS", None, None)


def test_login_with_unknown_email_is_refused(dao):
  assert AuthenticationManagerCTL.login(email=new_email(), password=PASSWORD) == ("INVALID_CREDENTIALS", None, None)


def test_login_with_invalid_token_is_refused(dao):
  assert AuthenticationManagerCTL.login(email="", token="not-a-token") == ("INVALID_TOKEN", None, None)


def test_registration_creates_a_user_pending_email_validation(dao):
  email = new_email()

  state, user_id = AuthenticationManagerCTL.register(user=User(name="Ann", email=email, password=PASSWORD))

  user = dao.find_by_id(entity=User, id=user_id)
  assert state == "VALIDATE_EMAIL"
  assert user.state == "VALIDATE_EMAIL"
  assert AuthorizationHandler().verify_password(PASSWORD, user.password)
  assert dao.find_by_id(entity=Profile, id=user_id).roles == ["user"]


def test_registration_with_weak_password_is_refused(dao):
  email = new_email()

  assert AuthenticationManagerCTL.register(user=User(name="Ann", email=email, password="password")) == ("WEAK_PASSWORD", None)
  assert list(dao.find_by_key_value(entity=User, key="email", value=email)) == []


def test_registration_of_an_active_email_is_refused(dao):
  _, email = active_user(dao)

  state, _ = AuthenticationManagerCTL.register(user=User(name="Ann", email=email, password=PASSWORD))

  assert state == "USER_ALREADY_REGISTERED"


def test_activation_with_the_emailed_code_lets_the_user_login(dao):
  email = new_email()
  _, user_id = AuthenticationManagerCTL.register(user=User(name="Ann", email=email, password=PASSWORD))

  assert AuthenticationManagerCTL.activate(user_id=user_id, code=stored_code(dao, email)) == "ACTIVE"
  assert AuthenticationManagerCTL.login(email=email, password=PASSWORD)[0] == "CONNECTED"


def test_activation_with_a_wrong_code_keeps_the_user_pending(dao):
  email = new_email()
  _, user_id = AuthenticationManagerCTL.register(user=User(name="Ann", email=email, password=PASSWORD))
  wrong_code = "111111" if stored_code(dao, email) != "111111" else "222222"

  assert AuthenticationManagerCTL.activate(user_id=user_id, code=wrong_code) == "INVALID_CODE"
  assert dao.find_by_id(entity=User, id=user_id).state == "VALIDATE_EMAIL"


def test_activation_attempts_cannot_lock_an_active_account(dao):
  user_id, email = active_user(dao)

  for _ in range(4):
    assert AuthenticationManagerCTL.activate(user_id=user_id, code="123456") == "USER_NOT_FOUND"

  assert dao.find_by_id(entity=User, id=user_id).state == "ACTIVE"
  assert AuthenticationManagerCTL.login(email=email, password=PASSWORD)[0] == "CONNECTED"


def test_the_cleared_code_cannot_be_exchanged_for_a_reset_token(dao):
  _, email = active_user(dao)

  assert AuthenticationManagerCTL.match_email_validation_code(email=email, code="----") == ("INVALID_CODE", None)


def test_password_reset_with_the_emailed_code(dao):
  _, email = active_user(dao)

  assert AuthenticationManagerCTL.send_email_validation_code(email=email) == "EMAIL_VALIDATION_CODE_SENT"
  state, token = AuthenticationManagerCTL.match_email_validation_code(email=email, code=stored_code(dao, email))
  assert state == "VALID_CODE"
  assert AuthenticationManagerCTL.reset_password(token=token, password=NEW_PASSWORD) == "PASSWORD_RESET"
  assert AuthenticationManagerCTL.login(email=email, password=NEW_PASSWORD)[0] == "CONNECTED"
  assert AuthenticationManagerCTL.login(email=email, password=PASSWORD)[0] == "INVALID_CREDENTIALS"


def test_guessing_reset_codes_is_rate_limited_across_fresh_codes(dao):
  _, email = active_user(dao)
  AuthenticationManagerCTL.send_email_validation_code(email=email)
  for _ in range(3):
    AuthenticationManagerCTL.match_email_validation_code(email=email, code="wrong")
  AuthenticationManagerCTL.send_email_validation_code(email=email)

  assert AuthenticationManagerCTL.match_email_validation_code(email=email, code=stored_code(dao, email)) == ("TOO_MANY_ATTEMPTS", None)


def test_password_reset_with_a_forged_token_is_refused(dao):
  assert AuthenticationManagerCTL.reset_password(token="not-a-token", password=NEW_PASSWORD) == "INVALID_TOKEN"


def test_validation_code_for_an_unknown_email(dao):
  assert AuthenticationManagerCTL.send_email_validation_code(email=new_email()) == "EMAIL_NOT_FOUND"


def test_preregistration_assigns_the_roles_and_waits_for_validation(dao):
  email = new_email()

  state, user_id = AuthenticationManagerCTL.preregister(user=User(name="Ann", email=email), roles=["admin"])

  assert state == "PREREGISTERED"
  assert dao.find_by_id(entity=User, id=user_id).state == "PREREGISTERED"
  assert dao.find_by_id(entity=Profile, id=user_id).roles == ["admin"]


def test_a_preregistered_user_onboards_by_setting_a_password(dao):
  email = new_email()
  AuthenticationManagerCTL.preregister(user=User(name="Ann", email=email), roles=["user"])

  assert AuthenticationManagerCTL.login(email=email, password=PASSWORD) == ("EMAIL_VALIDATION_CODE_SENT", None, None)
  _, token = AuthenticationManagerCTL.match_email_validation_code(email=email, code=stored_code(dao, email))
  assert AuthenticationManagerCTL.reset_password(token=token, password=PASSWORD) == "PASSWORD_RESET"
  assert AuthenticationManagerCTL.login(email=email, password=PASSWORD)[0] == "CONNECTED"
