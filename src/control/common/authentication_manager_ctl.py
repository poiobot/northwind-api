from domain.model import User
from data.generic_dao import GenericDAO
from services.authorization.authorization_handler import AuthorizationHandler
from services.authorization.authentication_service import AuthenticationService
from services.authorization.registration_service import RegistrationService
from services.authorization.password_reset_service import PasswordResetService
from services.authorization.oauth_service import OAuthService
from services.authorization.domain.enums import UserState
from services.authorization.domain.exceptions import AuthenticationError, UserNotFoundError, TooManyAttemptsError, RateLimitExceededError
from services.authorization.utils.audit_logger import audit_logger
from services.authorization.utils.rate_limiter import code_validation_rate_limiter
from services.email.email_service import EmailService

from typing import Tuple, List, Any
import logging

logging.basicConfig(level=logging.INFO)

# A code that has been used is replaced by this marker, which must never match
USED_CODE = "----"


class AuthenticationManagerCTL:
    """
    Serves the authentication router's (state, ...) contract with services.authorization.
    A refused operation returns its AuthenticationError code, e.g. INVALID_CREDENTIALS or WEAK_PASSWORD.
    """

    dao = GenericDAO()
    auth_handler = AuthorizationHandler()

    @classmethod
    def _service(cls, service):
        return service(dao=cls.dao, auth_handler=cls.auth_handler, email_service=EmailService, audit_logger=audit_logger)

    @classmethod
    def preregister(cls, user: User, roles: List[str]=None, **profile_payload) -> Tuple[str, str or None]:
        try:
            response = cls._service(RegistrationService).preregister(user=user, roles=roles, **profile_payload)
        except AuthenticationError as e:
            return e.code, None
        return response.operation, response.user_id

    @classmethod
    def register(cls, user: User) -> Tuple[str, str or None]:
        try:
            response = cls._service(RegistrationService).register(user=user)
        except AuthenticationError as e:
            return e.code, None
        # The user must now validate the email with the code sent to it
        return UserState.VALIDATE_EMAIL.value, response.user_id

    @classmethod
    def activate(cls, user_id: str, code: str) -> str:
        user = cls.dao.find_by_id(entity=User, id=user_id)
        # Only a registration waiting for its code can be activated: wrong codes sent for any other
        # account would use up its attempts and lock it
        if user is None or user.state != UserState.VALIDATE_EMAIL:
            return "USER_NOT_FOUND"
        try:
            cls._service(AuthenticationService).activate(user_id=user_id, code=code)
        except (TooManyAttemptsError, RateLimitExceededError):
            return "REGISTER_AGAIN"
        except AuthenticationError as e:
            return e.code
        return UserState.ACTIVE.value

    @classmethod
    def login(cls, email: str, password: str=None, token: str = None) -> Tuple[str, Any or None, str or None]:
        try:
            if token:
                response = OAuthService(dao=cls.dao, auth_handler=cls.auth_handler, audit_logger=audit_logger).oauth_login(oauth_token=token)
            else:
                response = cls._service(AuthenticationService).login(email=email, password=password or "")
        except AuthenticationError as e:
            return e.code, None, None
        # A preregistered user gets a validation code instead of a session
        if not response.success:
            return response.operation, None, None
        return response.operation, response.profile, response.token

    @classmethod
    def send_email_validation_code(cls, email: str) -> str:
        try:
            cls._service(AuthenticationService).send_validation_code(email=email)
        except UserNotFoundError:
            return "EMAIL_NOT_FOUND"
        return "EMAIL_VALIDATION_CODE_SENT"

    @classmethod
    def match_email_validation_code(cls, email: str, code: str) -> Tuple[str, str or None]:
        """
        Exchanges the code emailed to a user for a token that lets them set a new password.
        """
        email = email.lower()
        # Limits guessing across freshly sent codes too, which reset the user's attempts
        if not code_validation_rate_limiter.record_attempt(email):
            return "TOO_MANY_ATTEMPTS", None
        users = list(cls.dao.find_by_key_value(entity=User, key="email", value=email))
        if not users:
            return "USER_NOT_FOUND", None
        user = users[0]
        if user.attempts <= 0:
            return "TOO_MANY_ATTEMPTS", None
        if user.code in (None, USED_CODE) or user.code != code:
            user.attempts -= 1
            cls.dao.update(entity=User, id=user.id, data=user)
            return "INVALID_CODE", None
        user.code = USED_CODE
        user.attempts = 3
        cls.dao.update(entity=User, id=user.id, data=user)
        code_validation_rate_limiter.reset(email)
        return "VALID_CODE", cls.auth_handler.encode_single_use_token(user.id, expiry_days=1)

    @classmethod
    def reset_password(cls, token: str, password: str) -> str:
        try:
            cls._service(PasswordResetService).reset_password(token=token, new_password=password)
        except AuthenticationError as e:
            return e.code
        # The token proves the user reads that mailbox, which completes a registration still waiting for it
        user = cls.dao.find_by_id(entity=User, id=cls.auth_handler.decode_single_use_token(token)["data"])
        if user.state in (UserState.PREREGISTERED, UserState.VALIDATE_EMAIL):
            user.state = UserState.ACTIVE.value
            cls.dao.update(entity=User, id=user.id, data=user)
        return "PASSWORD_RESET"
