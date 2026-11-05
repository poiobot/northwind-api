import mimetypes
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Union, List
import logging

from api import settings

EMAIL_SERVER_ADDRESS = settings.EMAIL_SERVER_ADDRESS
EMAIL_FROM_ADDRESS = settings.EMAIL_FROM_ADDRESS
EMAIL_API_TOKEN = settings.EMAIL_API_TOKEN

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmailService:

    @classmethod
    def _validate_email(cls, email: str) -> bool:
        """Basic email validation"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    @classmethod
    def _prepare_recipients(cls, emails: Union[str, List[str]]) -> List[str]:
        """Convert single email or list of emails to validated list"""
        if isinstance(emails, str):
            recipients = [emails]
        else:
            recipients = emails

        # Validate all email addresses
        valid_recipients = []
        for email in recipients:
            email = email.strip()
            if cls._validate_email(email):
                valid_recipients.append(email)
            else:
                logger.warning(f"Invalid email address skipped: {email}")

        if not valid_recipients:
            raise ValueError("No valid email addresses provided")

        return valid_recipients

    @classmethod
    def _add_attachments(cls, msg: EmailMessage, attachments: Union[str, List[str]]) -> None:
        """Add single attachment or multiple attachments to email message"""
        if isinstance(attachments, str):
            attachment_list = [attachments]
        else:
            attachment_list = attachments

        for attachment_path in attachment_list:
            try:
                path = Path(attachment_path)

                if not path.exists():
                    logger.error(f"Attachment not found: {attachment_path}")
                    continue

                if not path.is_file():
                    logger.error(f"Attachment is not a file: {attachment_path}")
                    continue

                # Check file size (limit to 25MB)
                file_size = path.stat().st_size
                if file_size > 25 * 1024 * 1024:  # 25MB in bytes
                    logger.error(f"Attachment too large (>25MB): {attachment_path}")
                    continue

                with open(path, "rb") as attachment_file:
                    file_data = attachment_file.read()
                    filename = path.name

                    # Detect MIME type
                    mime_type, _ = mimetypes.guess_type(attachment_path)
                    if mime_type:
                        maintype, subtype = mime_type.split("/", 1)
                    else:
                        maintype, subtype = "application", "octet-stream"

                    msg.add_attachment(
                        file_data,
                        maintype=maintype,
                        subtype=subtype,
                        filename=filename
                    )
                    logger.info(f"Added attachment: {filename} ({file_size} bytes)")

            except Exception as e:
                logger.error(f"Failed to add attachment {attachment_path}: {e}")
                continue


    @classmethod
    def send_message(cls, email: Union[str, List[str]], subject: str, message: str, attachment_path: str = None):
        try:
            recipients = cls._prepare_recipients(email)

            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = EMAIL_FROM_ADDRESS
            msg["To"] = email

            msg.set_content(message)

            # Add attachments if provided
            if attachment_path:
                cls._add_attachments(msg, attachment_path)

            with smtplib.SMTP_SSL(EMAIL_SERVER_ADDRESS, 465) as smtp:
                smtp.login(EMAIL_FROM_ADDRESS, EMAIL_API_TOKEN)
                smtp.send_message(msg=msg)
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    @staticmethod
    def send_validation_code(uname: str, email: str, code: str):
        msg = EmailMessage()
        msg["Subject"] = "House-Keeper email code verification"
        msg["From"] = EMAIL_FROM_ADDRESS
        msg["To"] = email

        msg.set_content(
            f"Hi {uname}, please introduce code {code} to validate your email."
        )

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(EMAIL_FROM_ADDRESS, EMAIL_API_TOKEN)
            smtp.send_message(msg=msg)


if __name__ == "__main__":
    # EmailService.send_validation_code(uname="Rusty", email="jose.najera@gmail.com", code="9876")
    EmailService().send_message(email=["jose.najera@gmail.com", "jose@padmi.es"], subject="reports", message="test", attachment_path="/Users/jnajera/Downloads/WhatsApp Image 2025-08-30 at 11.58.18.jpg")

