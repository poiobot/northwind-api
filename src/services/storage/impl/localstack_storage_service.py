from services.storage.storage_service_interface import IStorageService

import logging
import boto3

from api import settings

logging.basicConfig(level=logging.INFO)

LOCALSTACK_REGION = settings.AWS_REGION
LOCALSTACK_ENDPOINT_URL = settings.LOCALSTACK_ENDPOINT_URL


class LocalStackStorageService(IStorageService):
    handler = boto3.client(
        "s3",
        region_name=LOCALSTACK_REGION,  # Any valid AWS region
        endpoint_url=LOCALSTACK_ENDPOINT_URL  # LocalStack S3 endpoint
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

    def upload(self, file_path: str, target_path: str, volume: str) -> str or None:
        try:
            self.handler.upload_file(file_path, volume, target_path)
            logging.info(f"self.upload({file_path}, {volume}, {target_path})")

            url = self.handler.generate_presigned_url(
                ClientMethod="get_object", Params={"Bucket": volume, "Key": target_path}
            )
            logging.info(f"File url is {url}")
            return url
        except FileNotFoundError:
            logging.info(f"The file {file_path} was not found.")
        except Exception as e:
            logging.info(msg=e)
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
