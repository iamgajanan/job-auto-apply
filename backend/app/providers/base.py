from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderCapabilities:
    easy_apply: bool = False
    remote: bool = False
    salary: bool = False
    login: bool = False


class BaseProvider(ABC):

    name = ""

    capabilities = ProviderCapabilities()

    def validate_request(self, request):
        """
        Override in providers if validation is needed.
        """
        return

    @abstractmethod
    def search(self, request):
        pass