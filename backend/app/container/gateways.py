from app.gateway.cache import SearchCache
from app.gateway.limiter import RateLimiter


class GatewayContainer:

    def __init__(self):
        self.cache = SearchCache()
        self.limiter = RateLimiter()