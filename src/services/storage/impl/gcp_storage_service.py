from services.storage.storage_service_interface import IStorageService
from google.cloud import storage
from google.api_core.exceptions import GoogleAPIError, NotFound, Forbidden
import logging
from typing import Optional
from bson import ObjectId
from datetime import timedelta

logging.basicConfig(level=logging.INFO)

from api import settings


class GCPStorageService(IStorageService):

    def __init__(self, credentials_path: str=settings.GCP_PROJECT_CREDENTIALS):
        """
        Initializes storage service in Google Cloud Storage.

        :param credentials_path: Path to JSON credentials file.
        """
        self.client = storage.Client.from_service_account_json(credentials_path)

    def mount(self, volume: str) -> Optional[int]:
        """
        Create a new bucket in GCP Storage.

        :param volume: Name of the bucket
        :return: Simulated HTTP code (201 for success) or None if error.
        """
        try:
            bucket = self.client.bucket(volume)
            self.client.create_bucket(bucket)
            logging.info(f"Volume '{volume}' successfully created.")
            return 201  # HTTP 201 Created
        except GoogleAPIError as e:
            logging.info(f"Volume {volume} already exists")
            return 200
        return None

    def unmount(self, volume: str) -> Optional[int]:
        """
        Removes bucket from GCP Storage.

        :param volume: Name of the bucket
        :return: Simulated HTTP code (204 for success) or None if error.
        """
        try:
            bucket = self.client.bucket(volume)
            bucket.delete()
            logging.info(f"Volume '{volume}' deleted.")
            return 204  # HTTP 204 No Content
        except NotFound:
            logging.error(f"Volume '{volume}' not found.")
        except Forbidden:
            logging.error(f"You don't have permissions to delete volume '{volume}'.")
        except GoogleAPIError as e:
            logging.error(f"Error while eliminating volume '{volume}': {e}")
        return None

    def upload(self, file_path: str, target_path: str, volume: str) -> Optional[str]:
        """
        Uploads a file to a bucket in GCP Storage and returns object id

        :param file_path: Local path to upload file
        :param target_path: Target path in the bucket on GCP
        :param volume: Bucket name
        :return: Unique id of uploaded object
        """
        try:
            bucket = self.client.bucket(volume)
            normalized_target_path = target_path.strip("/")
            normalized_target_path = f"{normalized_target_path}/{file_path.split('/')[-1]}"
            blob = bucket.blob(normalized_target_path)
            blob.upload_from_filename(file_path)
            logging.info(f"File '{file_path}' uploaded to '{volume}/{target_path}'.")

            oid = blob.name
            logging.info(f"Object id: {oid}")
            return oid
        except FileNotFoundError:
            logging.error(f"File '{file_path}' could not be found.")
        except GoogleAPIError as e:
            logging.error(f"Error while uploading file '{file_path}': {e}")
        return None

    def download(self, file_path: str, target_file_path: str, volume: str) -> bool:
        """
        Downloads file from GCP Storage bucket.

        :param file_path: File path within bucket
        :param target_file_path: Local path where file will be saved
        :param volume: Name of the bucket
        :return: True if successful download, False otherwise.
        """
        try:
            bucket = self.client.bucket(volume)
            blob = bucket.blob(file_path)
            blob.download_to_filename(target_file_path)
            logging.info(f"File '{file_path}' downloaded to '{target_file_path}'.")
            return True
        except NotFound:
            logging.error(f"File '{file_path}' could not be located in '{volume}'.")
        except GoogleAPIError as e:
            logging.error(f"Error while downloading '{file_path}': {e}")
        return False

    def delete(self, file_path: str, volume: str) -> Optional[int]:
        """
        Deletes a file from a bucket in GCP Storage.

        :param file_path: object file path with bucket
        :param volume: Bucket name
        :return: Simulated HTTP code (204 for success) or None if error.
        """
        try:
            bucket = self.client.bucket(volume)
            blob = bucket.blob(file_path)
            blob.delete()
            logging.info(f"File '{file_path}' deleted from '{volume}'.")
            return 204  # HTTP 204 No Content
        except NotFound:
            logging.error(f"File '{file_path}' could not be located in '{volume}'.")
        except GoogleAPIError as e:
            logging.error(f"Error while eliminating '{file_path}': {e}")
        return None

    def get_file_url(self, volume: str, file_path: str, expiration_minutes: int = 60) -> Optional[str]:
        """
        Generates a presigned URL for a GCS object.

        :param bucket_name: Name of the bucket.
        :param object_name: The object (file) name in the bucket.
        :param expiration_minutes: URL expiration time in minutes (default: 60 min).
        :return: Presigned URL for temporary access or empty string if an error occurs.
        """
        try:
            bucket = self.client.bucket(volume)
            blob = bucket.blob(file_path)

            if not blob.exists():
                logging.error(f"File '{file_path}' not found in volume '{volume}'.")
                return ""

            # Generate a signed URL valid for expiration_minutes
            url = blob.generate_signed_url(expiration=timedelta(minutes=expiration_minutes))

            logging.info(f"Presigned URL generated: {url}")
            return url

        except Exception as e:
            logging.error(f"Error generating presigned URL for '{file_path}': {e}")
            return ""


if __name__ == '__main__':

    handler = GCPStorageService()
    handler.mount(volume='keeper-domain-ok-storage')
    oid = handler.upload(volume='keeper-domain-ok-storage', file_path='/Users/jnajera/Downloads/green_monster.jpg', target_path='avatars')
    handler.download(volume='keeper-domain-ok-datastorage', file_path=oid, target_file_path="/tmp/image.png")
    url = handler.get_file_url(volume='keeper-domain-ok-storage', file_path=oid, expiration_minutes=60)
    print(url)
    # handler.delete(volume='padmi-datastorage', file_path=oid)
