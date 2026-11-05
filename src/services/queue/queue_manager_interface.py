from abc import ABC, abstractmethod

from typing import Dict


class IQueueManager(ABC):

    @abstractmethod
    def create_queue(self, queue_name: str):
        """ """

    @abstractmethod
    def write(self, queue_name: str, msg: str):
        """ """

    @abstractmethod
    def read(self, queue_name: str):
        """ """

    @abstractmethod
    def purge(self, queue_name: str):
        """ """

    @abstractmethod
    def delete(self, queue_name: str):
        """ """

    @abstractmethod
    def list_queues(self) -> Dict:
        """ """


class IQueueFactory(ABC):

    @abstractmethod
    def get_service(provider: str) -> IQueueManager:
        """ """