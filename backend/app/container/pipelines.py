from app.features.audit.service import AuditService
from app.features.jobs.pipeline import SearchPipeline


class PipelineContainer:

    def __init__(
        self,
        repositories,
        gateways,
        providers,
    ):
        self.search = SearchPipeline(
            repository=repositories.jobs,
            audit_service=AuditService(
                repositories.audit,
            ),
            cache=gateways.cache,
            limiter=gateways.limiter,
            engine=providers.search_engine,
        )