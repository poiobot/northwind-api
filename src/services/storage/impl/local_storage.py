from services.storage.storage_service_interface import IStorageService

import os
import shutil
import logging
from typing import Optional

from api import settings

logging.basicConfig(level=logging.INFO)

LOCAL_STORAGE_PATH = getattr(settings, 'LOCAL_STORAGE_PATH', '/tmp/storage')


class LocalStorageService(IStorageService):

    def __init__(self):
        self.base_path = LOCAL_STORAGE_PATH

    def _volume_path(self, volume: str) -> str:
        return os.path.join(self.base_path, volume)

    def mount(self, volume: str) -> int or None:
        volume_path = self._volume_path(volume)
        try:
            os.makedirs(volume_path, exist_ok=True)
            logging.info(f"Volume '{volume}' mounted at '{volume_path}'.")
            return 200
        except OSError as e:
            logging.error(f"Error mounting volume '{volume}': {e}")
        return None

    def unmount(self, volume: str) -> int or None:
        volume_path = self._volume_path(volume)
        try:
            if os.path.exists(volume_path):
                shutil.rmtree(volume_path)
                logging.info(f"Volume '{volume}' unmounted (removed '{volume_path}').")
            return 200
        except OSError as e:
            logging.error(f"Error unmounting volume '{volume}': {e}")
        return None

    def upload(self, file_path: str, target_path: str, volume: str) -> Optional[str]:
        """
        Copies a local file into the volume directory and returns the object key.

        :param file_path: Local path of the file to upload
        :param target_path: Target subdirectory inside the volume
        :param volume: Volume (directory) name
        :return: Object key (relative path within the volume) or None on failure
        """
        try:
            normalized_target_path = target_path.strip("/")
            dest_dir = os.path.join(self._volume_path(volume), normalized_target_path)
            os.makedirs(dest_dir, exist_ok=True)

            filename = os.path.basename(file_path)
            object_key = f"{normalized_target_path}/{filename}"
            dest_file = os.path.join(self._volume_path(volume), object_key)

            shutil.copy2(file_path, dest_file)

            logging.info(f"File '{file_path}' uploaded to '{dest_file}'.")
            logging.info(f"Object key: {object_key}")
            return object_key

        except FileNotFoundError:
            logging.error(f"File '{file_path}' could not be found.")
        except OSError as e:
            logging.error(f"Error uploading file '{file_path}': {e}")
        except Exception as e:
            logging.error(f"Unexpected error uploading file '{file_path}': {e}")

        return None

    def download(self, file_path: str, target_file_path: str, volume: str) -> str or None:
        try:
            source = os.path.join(self._volume_path(volume), file_path)
            os.makedirs(os.path.dirname(target_file_path), exist_ok=True)
            shutil.copy2(source, target_file_path)
            logging.info(f"File '{file_path}' downloaded to '{target_file_path}'.")
            return target_file_path
        except FileNotFoundError:
            logging.error(f"File '{file_path}' not found in volume '{volume}'.")
        except Exception as e:
            logging.error(f"Error downloading file '{file_path}': {e}")
        return None

    def delete(self, file_path: str, volume: str) -> str:
        target = os.path.join(self._volume_path(volume), file_path)
        try:
            if os.path.exists(target):
                os.remove(target)
                logging.info(f"File '{file_path}' deleted from volume '{volume}'.")
            return 200
        except Exception as e:
            logging.error(f"Error deleting file '{file_path}': {e}")
        return None

    def get_file_url(self, volume: str, file_path: str, expires: int = 60) -> str:
        """
        Returns the absolute filesystem path for a file in the volume.

        :param volume: Volume (directory) name
        :param file_path: Object key (relative path within the volume)
        :param expires: Ignored for local storage
        :return: Absolute path to the file, or empty string if not found
        """
        target = os.path.join(self._volume_path(volume), file_path)
        if os.path.exists(target):
            return target
        logging.error(f"File '{file_path}' not found in volume '{volume}'.")
        return ""
