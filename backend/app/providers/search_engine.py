from concurrent.futures import ThreadPoolExecutor, as_completed

from app.providers.registry import ProviderRegistry


class SearchEngine:
    def __init__(self):
        self.registry = ProviderRegistry()

    def _search_provider(self, provider, request):
        provider.validate_request(request)
        return provider.search(request) or []

    def search(self, request):
        if request.platform.lower() != "all":
            provider = self.registry.get(request.platform)
            return self._search_provider(provider, request)

        providers = self.registry.get_all()
        if len(providers) <= 1:
            return self._search_provider(providers[0], request) if providers else []

        # LinkedIn and Naukri are independent browser/network operations. Run
        # them concurrently so an "all" search costs roughly the slower
        # provider, not the sum of both provider latencies.
        jobs = []
        with ThreadPoolExecutor(max_workers=len(providers), thread_name_prefix="job-provider") as executor:
            futures = [executor.submit(self._search_provider, provider, request) for provider in providers]
            for future in as_completed(futures):
                jobs.extend(future.result())
        return jobs
