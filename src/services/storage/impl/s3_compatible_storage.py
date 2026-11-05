"""
S3-compatible storage service — works with AWS S3, Cloudflare R2, MinIO, etc.

Uses S3_ACCESS_KEY, S3_SECRET_KEY, S3_ENDPOINT, S3_REGION from settings.
"""
from services.storage.storage_service_interface import IStorageService

import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
from typing import Optional
import logging

from api import settings

logging.basicConfig(level=logging.INFO)


class S3CompatibleStorageService(IStorageService):

    def __init__(self):
        kwargs = {
            "aws_access_key_id": settings.S3_ACCESS_KEY,
            "aws_secret_access_key": settings.S3_SECRET_KEY,
            "region_name": settings.S3_REGION or "auto",
        }
        if settings.S3_ENDPOINT:
            kwargs["endpoint_url"] = settings.S3_ENDPOINT
        kwargs["config"] = Config(signature_version="s3v4")
        self.handler = boto3.client("s3", **kwargs)

    def mount(self, volume: str) -> int or None:
        try:
            self.handler.head_bucket(Bucket=volume)
            logging.info(f"Bucket {volume} exists and is accessible.")
            return 200
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code == "404":
                try:
                    self.handler.create_bucket(Bucket=volume)
                    logging.info(f"Bucket {volume} created.")
                    return 201
                except Exception as ce:
                    logging.error(f"Failed to create bucket {volume}: {ce}")
            else:
                logging.error(f"Bucket {volume} error: {e}")
        return None

    def unmount(self, volume: str) -> int or None:
        return None  # don't delete buckets

    def upload(self, file_path: str, target_path: str, volume: str) -> str or None:
        try:
            self.handler.upload_file(file_path, volume, target_path)
            logging.info(f"Uploaded {file_path} → {volume}/{target_path}")
            return target_path
        except Exception as e:
            logging.error(f"Upload failed: {e}")
            return None

    def download(self, file_path: str, target_file_path: str, volume: str) -> str or None:
        try:
            self.handler.download_file(volume, file_path, target_file_path)
            return target_file_path
        except Exception as e:
            logging.error(f"Download failed: {e}")
            return None

    def delete(self, file_path: str, volume: str) -> str or None:
        try:
            self.handler.delete_object(Bucket=volume, Key=file_path)
            return file_path
        except Exception as e:
            logging.error(f"Delete failed: {e}")
            return None

    def get_file_url(self, volume: str, file_path: str, expires: int = 3600) -> Optional[str]:
        try:
            url = self.handler.generate_presigned_url(
                "get_object",
                Params={"Bucket": volume, "Key": file_path},
                ExpiresIn=expires,
            )
            return url
        except Exception as e:
            logging.error(f"URL generation failed: {e}")
            return None
