from app.providers.search_engine import SearchEngine


class ProviderContainer:

    def __init__(self):
        self.search_engine = SearchEngine()