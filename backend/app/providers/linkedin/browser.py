# Kept for backward compatibility -- the actual implementation now lives
# in app.providers.common.browser so it can be shared with other
# providers (e.g. Naukri) without one importing from the other.
from app.providers.common.browser import BrowserManager

__all__ = ["BrowserManager"]
