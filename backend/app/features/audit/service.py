import hashlib

from app.common.services.base_service import BaseService
from app.features.audit.model import SearchLog


class AuditService(BaseService):

    def log(
        self,
        *,
        provider: str,
        keyword: str,
        location: str,
        client_ip: str,
        response_source: str,
        jobs_found: int,
        duration_ms: int,
        status: str,
        error: str = "",
    ):

        request_hash = hashlib.sha256(
            f"{provider}:{keyword}:{location}".encode()
        ).hexdigest()

        log = SearchLog(
            provider=provider,
            keyword=keyword,
            location=location,
            client_ip=client_ip,
            request_hash=request_hash,
            response_source=response_source,
            jobs_found=jobs_found,
            duration_ms=duration_ms,
            status=status,
            error=error,
        )

        return self.repository.create(log)