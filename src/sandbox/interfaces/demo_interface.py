from abc import ABC, abstractmethod
from typing import Any


class IDemo(ABC):

    @abstractmethod
    def calculate(self, a: Any, b: Any, op: str) -> Any:
        """
        Makes a calculation between two numbers
        :param a: first number
        :param b: second number
        :param op: name of operation to apply
        :return: Result value
        """