from dataclasses import dataclass
from typing import Optional

@dataclass
class PlatformAccessError(RuntimeError):
    platform: str
    reason: str
    status_code: Optional[int] = None
    def __str__(self):
        suffix = f" (HTTP {self.status_code})" if self.status_code else ""
        return f"{self.platform} access stopped: {self.reason}{suffix}"


class BlockDetector:
    """Detect access restrictions; never attempts to bypass them."""

    BLOCK_STATUSES = {403, 429}
    CAPTCHA_MARKERS = (
        "captcha", "verify you are human", "security verification",
        "unusual activity", "challenge", "robot check",
    )

    LOGIN_URL_MARKERS = {
        "linkedin": ("/login", "/checkpoint/", "/authwall"),
        "naukri": ("/nlogin", "/login", "login?"),
    }

    @classmethod
    def check(cls, platform: str, page, response=None):
        platform = platform.lower()
        status = getattr(response, "status", None) if response is not None else None
        if status in cls.BLOCK_STATUSES:
            raise PlatformAccessError(platform, "upstream rejected the request", status)

        url = (getattr(page, "url", "") or "").lower()
        if any(marker in url for marker in cls.LOGIN_URL_MARKERS.get(platform, ())):
            raise PlatformAccessError(platform, "login/session verification required")

        # Keep inspection lightweight and only use visible page text/title.
        try:
            title = (page.title() or "").lower()
        except Exception:
            title = ""
        try:
            body = (page.locator("body").inner_text(timeout=1500) or "").lower()[:12000]
        except Exception:
            body = ""

        haystack = f"{title}\n{body}"
        if any(marker in haystack for marker in cls.CAPTCHA_MARKERS):
            raise PlatformAccessError(platform, "CAPTCHA/challenge detected")
