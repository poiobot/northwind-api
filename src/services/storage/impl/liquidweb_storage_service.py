from services.storage.storage_service_interface import IStorageService

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Optional
import logging

from api import settings

logging.basicConfig(level=logging.INFO)

LIQUIDWEB_ACCESS_KEY = settings.LIQUIDWEB_ACCESS_KEY
LIQUIDWEB_SECRET_KEY = settings.LIQUIDWEB_SECRET_KEY
LIQUIDWEB_ENDPOINT = settings.LIQUIDWEB_ENDPOINT


class LiquidWebStorageService(IStorageService):
    handler = boto3.client(
        "s3",
        aws_access_key_id=LIQUIDWEB_ACCESS_KEY,
        aws_secret_access_key=LIQUIDWEB_SECRET_KEY,
        endpoint_url=LIQUIDWEB_ENDPOINT,
    )

    def mount(self, volume: str) -> int or None:
        try:
            # Create the S3 bucket
            result = self.handler.create_bucket(Bucket=volume)
            logging.info(f"Bucket {volume} created successfully.")
            return result.get("ResponseMetadata", {}).get("HTTPStatusCode")
        except Exception as e:
            logging.info(msg=e)
        return None

    def unmount(self, volume: str) -> int or None:
        try:
            result = self.handler.delete_bucket(Bucket=volume)
            return result.get("ResponseMetadata", {}).get("HTTPStatusCode")
        except Exception as e:
            logging.info(msg=e)
        return None

    def upload(self, file_path: str, target_path: str, volume: str) -> Optional[str]:
        """
        Uploads a file to a bucket in AWS S3 and returns object key

        :param file_path: Local path to upload file
        :param target_path: Target path in the bucket on S3
        :param volume: Bucket name
        :return: Unique key of uploaded object
        """
        try:
            # Normalize target path and construct final object key
            normalized_target_path = target_path.strip("/")
            object_key = f"{normalized_target_path}/{file_path.split('/')[-1]}"

            # Upload file to S3
            self.handler.upload_file(Filename=file_path, Bucket=volume, Key=object_key)

            logging.info(f"File '{file_path}' uploaded to '{volume}/{target_path}'.")
            logging.info(f"Object key: {object_key}")
            return object_key

        except FileNotFoundError:
            logging.error(f"File '{file_path}' could not be found.")
        except NoCredentialsError:
            logging.error("AWS credentials not found.")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchBucket':
                logging.error(f"Bucket '{volume}' does not exist.")
            elif error_code == 'AccessDenied':
                logging.error(f"Access denied to bucket '{volume}'.")
            else:
                logging.error(f"Error while uploading file '{file_path}': {e}")
        except Exception as e:
            logging.error(f"Unexpected error while uploading file '{file_path}': {e}")

        return None

    def download(self, file_path: str, target_file_path: str, volume: str) -> str or None:
        try:
            with open(target_file_path, 'wb') as f:
                result = self.handler.download_fileobj(volume, file_path, f)
                print(result)
        except Exception as e:
            logging.info(msg=e)
        return None

    def delete(self, file_path: str, volume: str) -> str:
        result = self.handler.delete_object(Bucket=volume, Key=file_path)
        return result.get("ResponseMetadata", {}).get("HTTPStatusCode")

    def get_file_url(self, volume: str, file_path: str, expires: int = 60) -> str:
        """
        Generates a presigned URL for an S3 object.

        :param volume: Name of the S3 bucket.
        :param file_path: The object (file) key in the bucket.
        :param expires: URL expiration time in minutes (default: 60 min).
        :return: Presigned URL for temporary access or empty string if an error occurs.
        """
        try:
            # Check if object exists
            self.handler.head_object(Bucket=volume, Key=file_path)

            # Generate presigned URL valid for expires minutes
            url = self.handler.generate_presigned_url(
                ClientMethod='get_object',
                Params={'Bucket': volume, 'Key': file_path},
                ExpiresIn=expires * 60  # Convert minutes to seconds
            )
            return url

        except self.handler.exceptions.ClientError as e:
            if e.response['Error']['Code'] == '404':
                logging.error(f"File '{file_path}' not found in bucket '{volume}'.")
            else:
                logging.error(f"Error generating presigned URL for '{file_path}': {e}")
            return ""
        except Exception as e:
            logging.error(f"Error generating presigned URL for '{file_path}': {e}")
            return ""
