from abc import ABC, abstractmethod


class IStorageService(ABC):

    @abstractmethod
    def mount(self, volume: str) -> int or None:
        """ """

    @abstractmethod
    def unmount(self, volume: str) -> int or None:
        """ """

    @abstractmethod
    def upload(self, file_path: str, target_path: str, volume: str) -> str or None:
        """ """

    @abstractmethod
    def download(self, file_path: str, target_file_path: str, volume: str) -> str or None:
        """ """

    @abstractmethod
    def delete(self, file_path: str, volume: str) -> str or None:
        """ """

    # TODO: Add unmount volume
    # TODO: Add file remove, rename, copy, move functions


class IStorageServiceFactory(ABC):

    @abstractmethod
    def get_service(self, provider: str) -> IStorageService or None:
        """ """
