from fastapi import Depends, Query, Request
from fastapi.routing import APIRouter

from agent.monitoring.query import (
    TRACES_DEFAULT_LIMIT,
    TRACES_MAX_LIMIT,
    MonitoringQueryService,
    QueryDimensions,
)
from agent.monitoring.session import MonitoringSession, require_monitoring_session
from agent.schemas.monitoring_query import (
    AlertsResponse,
    Compare,
    DataQualityResponse,
    FeatureDriftResponse,
    Granularity,
    HeaderResponse,
    OverviewResponse,
    ReferenceProfileResponse,
    RuntimeResponse,
    SeverityFilter,
    TracesResponse,
    Window,
)

MONITORING_API_PREFIX = "/monitoring/api"


def get_query_service(request: Request) -> MonitoringQueryService:
    return request.app.state.monitoring_query


def _dimensions(
    window: Window = Window.H24,
    compare: Compare = Compare.REFERENCE,
    severity: SeverityFilter = SeverityFilter.ALL,
    granularity: Granularity = Granularity.AUTO,
    feature: str | None = None,
) -> QueryDimensions:
    return QueryDimensions(
        window=window,
        compare=compare,
        severity=severity,
        granularity=granularity,
        feature=feature,
    )


def build_query_router() -> APIRouter:
    router = APIRouter(prefix=MONITORING_API_PREFIX)

    @router.get("/header", response_model=HeaderResponse)
    async def header(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> HeaderResponse:
        return await service.header(session.deployment_id)

    @router.get("/overview", response_model=OverviewResponse)
    async def overview(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> OverviewResponse:
        return await service.overview(session.deployment_id, dims)

    @router.get("/runtime", response_model=RuntimeResponse)
    async def runtime(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> RuntimeResponse:
        return await service.runtime(session.deployment_id, dims)

    @router.get("/data-quality", response_model=DataQualityResponse)
    async def data_quality(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> DataQualityResponse:
        return await service.data_quality(session.deployment_id, dims)

    @router.get("/feature-drift", response_model=FeatureDriftResponse)
    async def feature_drift(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> FeatureDriftResponse:
        return await service.feature_drift(session.deployment_id, dims)

    @router.get("/reference-profile", response_model=ReferenceProfileResponse)
    async def reference_profile(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> ReferenceProfileResponse:
        return await service.reference_profile(session.deployment_id, dims)

    @router.get("/alerts", response_model=AlertsResponse)
    async def alerts(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> AlertsResponse:
        return await service.alerts(session.deployment_id, dims)

    @router.get("/traces", response_model=TracesResponse)
    async def traces(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        limit: int = Query(TRACES_DEFAULT_LIMIT, ge=1, le=TRACES_MAX_LIMIT),
        offset: int = Query(0, ge=0),
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> TracesResponse:
        return await service.traces(session.deployment_id, dims, limit=limit, offset=offset)

    return router
