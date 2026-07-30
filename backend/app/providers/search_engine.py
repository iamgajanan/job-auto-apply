from app.providers.registry import ProviderRegistry


class SearchEngine:

    def __init__(self):
        self.registry = ProviderRegistry()

    def search(self, request):

        jobs = []

        if request.platform.lower() == "all":
            providers = self.registry.get_all()
        else:
            providers = [
                self.registry.get(request.platform)
            ]

        for provider in providers:

            provider.validate_request(request)

            provider_jobs = provider.search(request)

            if provider_jobs:
                jobs.extend(provider_jobs)

        return jobs