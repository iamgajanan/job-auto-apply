from app.providers.registry import ProviderRegistry


class ProviderFactory:

    def __init__(self):
        self.registry = ProviderRegistry()

    def create(self, platform: str):
        return self.registry.get(platform)