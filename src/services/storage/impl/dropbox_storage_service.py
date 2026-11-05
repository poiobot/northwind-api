from storage_service_interface import IStorageService

import dropbox
import dropbox.files
from dropbox.exceptions import AuthError
from starlette import status

import logging

from api import settings

logging.basicConfig(level=logging.INFO)

DROPBOX_APP_KEY = settings.DROPBOX_APP_KEY
DROPBOX_APP_SECRET = settings.DROPBOX_APP_SECRET
DROPBOX_API_TOKEN = settings.DROPBOX_API_TOKEN


class DropboxStorageService(IStorageService):
    try:
        dbx = dropbox.Dropbox(DROPBOX_API_TOKEN)
    except AuthError as e:
        logging.info(msg="Error connecting to Dropbox with access token: " + str(e))

    def mount(self, volume: str) -> int or None:
        try:
            # Create the root directory for volume
            self.dbx.files_create_folder_v2(path=f"/{volume}")
            logging.info(f"Volume {volume} created successfully.")
            return status.HTTP_201_CREATED
        except dropbox.exceptions.ApiError:
            logging.info(msg=f"Volume /{volume} exists already")
        except Exception as e:
            logging.info(msg=e)
        return None

    def unmount(self, volume: str) -> int or None:
        try:
            return self.dbx.files_delete_v2(path=f"/{volume}")
        except Exception as e:
            logging.info(msg=e)
        return None

    def upload(self, file_path: str, target_path: str, volume="keeper-domain-ok-data-store") -> str or None:
        # TODO: Create folders automatically if those do not exist
        try:
            with open(file_path, "rb") as f:
                data = f.read()
                self.dbx.files_upload(data, path=f"/{volume}/{target_path}")
                logging.info(f"DropboxStorageService.upload({file_path}, {volume}, {target_path})")
            url = self.dbx.sharing_create_shared_link_with_settings(f"/{volume}/{target_path}").url
            logging.info(f"File url is {url}")
            return url.replace('?dl=0', '?dl=1')
        except FileNotFoundError:
            logging.info(f"The file {file_path} was not found.")
        except dropbox.exceptions.ApiError as exception:
            if exception.error.is_shared_link_already_exists():
                shared_link_metadata = self.dbx.sharing_list_shared_links(f"/{volume}/{target_path}")
                shared_link = shared_link_metadata.links[0].url
                return shared_link.replace('?dl=0', '?dl=1')
        except Exception as e:
            logging.info(msg=e)
        return None

    def download(self, file_path: str, target_file_path: str, volume: str) -> str:
        pass

    def delete(self, file_path: str, volume: str) -> str:
        pass
