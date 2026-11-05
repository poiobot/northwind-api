"""
Clerk Service for backend user management.

Wraps the Clerk Backend API for creating and managing users
that authenticate via Telegram (no password, no browser flow).
"""

import logging
from typing import Optional, Tuple
from clerk_backend_api import Clerk
from clerk_backend_api.models import ClerkErrors

from api import settings

logger = logging.getLogger(__name__)


class ClerkService:
    """
    Manages Clerk users for Telegram bot integration.

    Users are created via the Backend API with external_id set to their
    Telegram user ID. No password is required since auth happens through
    Telegram identity.
    """

    def __init__(self, secret_key: str = None):
        self.client = Clerk(bearer_auth=secret_key or settings.CLERK_SECRET_KEY)

    def create_user(
        self,
        telegram_user_id: str,
        first_name: str = None,
        last_name: str = None,
        email: str = None,
    ) -> Tuple[str, dict]:
        """
        Create a Clerk user for a Telegram bot user.

        Uses telegram_user_id as external_id so we can look them up later.

        :param telegram_user_id: Telegram user ID (used as external_id)
        :param first_name: User's first name from Telegram
        :param last_name: User's last name from Telegram
        :param email: Optional email address
        :return: Tuple of (status, user_dict or error_message)
        """
        try:
            kwargs = {
                "external_id": str(telegram_user_id),
                "skip_password_requirement": True,
            }
            if first_name:
                kwargs["first_name"] = first_name
            if last_name:
                kwargs["last_name"] = last_name
            if email:
                kwargs["email_address"] = [email]

            user = self.client.users.create(**kwargs)

            logger.info(f"Clerk user created: {user.id} for telegram_user_id={telegram_user_id}")
            return "USER_CREATED", {
                "clerk_user_id": user.id,
                "external_id": user.external_id,
                "first_name": user.first_name,
                "last_name": user.last_name,
            }

        except ClerkErrors as e:
            logger.error(f"Clerk API error creating user: {e}")
            return "CLERK_ERROR", str(e)

        except Exception as e:
            logger.error(f"Unexpected error creating Clerk user: {e}")
            return "ERROR", str(e)

    def get_user_by_telegram_id(self, telegram_user_id: str) -> Tuple[str, dict]:
        """
        Look up a Clerk user by their Telegram user ID (external_id).

        :param telegram_user_id: Telegram user ID
        :return: Tuple of (status, user_dict or None)
        """
        try:
            users = self.client.users.list(request={
                "external_id": [str(telegram_user_id)]
            })

            user_list = list(users) if users else []
            if not user_list:
                return "USER_NOT_FOUND", None

            user = user_list[0]
            return "USER_FOUND", {
                "clerk_user_id": user.id,
                "external_id": user.external_id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email_addresses[0].email_address if user.email_addresses else None,
            }

        except ClerkErrors as e:
            logger.error(f"Clerk API error looking up user: {e}")
            return "CLERK_ERROR", str(e)

        except Exception as e:
            logger.error(f"Unexpected error looking up Clerk user: {e}")
            return "ERROR", str(e)

    def get_user(self, clerk_user_id: str) -> Tuple[str, dict]:
        """
        Get a Clerk user by their Clerk user ID.

        :param clerk_user_id: Clerk's internal user ID
        :return: Tuple of (status, user_dict or None)
        """
        try:
            user = self.client.users.get(user_id=clerk_user_id)
            if not user:
                return "USER_NOT_FOUND", None

            return "USER_FOUND", {
                "clerk_user_id": user.id,
                "external_id": user.external_id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email_addresses[0].email_address if user.email_addresses else None,
            }

        except ClerkErrors as e:
            logger.error(f"Clerk API error getting user: {e}")
            return "CLERK_ERROR", str(e)

        except Exception as e:
            logger.error(f"Unexpected error getting Clerk user: {e}")
            return "ERROR", str(e)

    def delete_user(self, clerk_user_id: str) -> Tuple[str, str]:
        """
        Delete a Clerk user.

        :param clerk_user_id: Clerk's internal user ID
        :return: Tuple of (status, clerk_user_id)
        """
        try:
            self.client.users.delete(user_id=clerk_user_id)
            logger.info(f"Clerk user deleted: {clerk_user_id}")
            return "USER_DELETED", clerk_user_id

        except ClerkErrors as e:
            logger.error(f"Clerk API error deleting user: {e}")
            return "CLERK_ERROR", str(e)

        except Exception as e:
            logger.error(f"Unexpected error deleting Clerk user: {e}")
            return "ERROR", str(e)
