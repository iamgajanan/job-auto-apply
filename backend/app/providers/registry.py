from app.providers.linkedin.search import LinkedInSearch
from app.providers.naukri.search import NaukriSearch


class ProviderRegistry:

    def __init__(self):
        self.providers = {}

        self.register("linkedin", LinkedInSearch())
        self.register("naukri", NaukriSearch())

    def register(self, name, provider):
        self.providers[name.lower()] = provider

    def get(self, platform):

        provider = self.providers.get(platform.lower())

        if provider is None:
            raise Exception(f"Unsupported provider: {platform}")

        return provider

    def get_all(self):
        return list(self.providers.values())

    def list(self):
        return list(self.providers.keys())