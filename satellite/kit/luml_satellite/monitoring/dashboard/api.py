import inspect
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.routing import APIRouter

from luml_satellite.monitoring.dashboard.query import (
    TRACES_DEFAULT_LIMIT,
    TRACES_MAX_LIMIT,
    MonitoringQueryService,
    QueryDimensions,
)
from luml_satellite.monitoring.dashboard.schemas import (
    AcknowledgeAlertRequest,
    AlertsResponse,
    Compare,
    DataQualityResponse,
    FeatureDriftResponse,
    Granularity,
    HeaderResponse,
    OutputDriftResponse,
    OverviewResponse,
    ReferenceProfileResponse,
    RuntimeResponse,
    SectionState,
    SeverityFilter,
    SortOrder,
    TraceDetailResponse,
    TraceSort,
    TracesResponse,
    Window,
    WorkerHealthResponse,
)
from luml_satellite.monitoring.dashboard.session import (
    MonitoringSession,
    require_monitoring_session,
    require_monitoring_write,
)

MONITORING_API_PREFIX = "/monitoring/api"
MONITORING_FACET = "deployment:monitoring"


class DeploymentNotHostedError(Exception):
    code = "deployment_not_hosted"
    detail = "Deployment not found on this Satellite"

    def __init__(self) -> None:
        super().__init__(self.detail)


def get_query_service(request: Request) -> MonitoringQueryService:
    return cast(MonitoringQueryService, request.app.state.monitoring_query)


_MAX_RANGE_SECONDS = 31 * 24 * 3600


def _dimensions(
    window: Window = Window.H24,
    compare: Compare = Compare.REFERENCE,
    severity: SeverityFilter = SeverityFilter.ALL,
    granularity: Granularity = Granularity.AUTO,
    feature: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    compare_start: datetime | None = None,
    compare_end: datetime | None = None,
) -> QueryDimensions:
    if (start is None) != (end is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start and end come together: pass both for a custom range, or neither",
        )
    if start is not None and end is not None:
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
        if end <= start:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="end must be after start",
            )
        if (end - start).total_seconds() > _MAX_RANGE_SECONDS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="range too wide: monitoring data is retained for 30 days",
            )
    if compare is Compare.CUSTOM:
        if compare_start is None or compare_end is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="compare=custom needs compare_start and compare_end",
            )
        if compare_start.tzinfo is None:
            compare_start = compare_start.replace(tzinfo=UTC)
        if compare_end.tzinfo is None:
            compare_end = compare_end.replace(tzinfo=UTC)
        if compare_end <= compare_start:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="compare_end must be after compare_start",
            )
        if (compare_end - compare_start).total_seconds() > _MAX_RANGE_SECONDS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="comparison range too wide: monitoring data is retained for 30 days",
            )
    return QueryDimensions(
        window=window,
        compare=compare,
        severity=severity,
        granularity=granularity,
        feature=feature,
        start=start,
        end=end,
        compare_start=compare_start if compare is Compare.CUSTOM else None,
        compare_end=compare_end if compare is Compare.CUSTOM else None,
    )


def build_query_router() -> APIRouter:
    router = APIRouter(prefix=MONITORING_API_PREFIX)

    @router.get(
        "/header",
        response_model=HeaderResponse,
        summary="Get the dashboard header",
        description="Return deployment identity, model kind, and reference-profile state.",
    )
    async def header(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> HeaderResponse:
        return await service.header(session.deployment_id)

    @router.get(
        "/overview",
        response_model=OverviewResponse,
        summary="Get the dashboard overview",
        description="Return a summary of monitoring results for the requested window.",
    )
    async def overview(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> OverviewResponse:
        return await service.overview(session.deployment_id, dims)

    @router.get(
        "/runtime",
        response_model=RuntimeResponse,
        summary="Get dashboard runtime metrics",
        description="Return request volume, latency, and error metrics for the requested window.",
    )
    async def runtime(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> RuntimeResponse:
        return await service.runtime(session.deployment_id, dims)

    @router.get(
        "/data-quality",
        response_model=DataQualityResponse,
        summary="Get dashboard data-quality metrics",
        description="Return input data-quality checks for the requested window.",
    )
    async def data_quality(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> DataQualityResponse:
        return await service.data_quality(session.deployment_id, dims)

    @router.get(
        "/feature-drift",
        response_model=FeatureDriftResponse,
        summary="Get dashboard feature-drift metrics",
        description="Return feature and multivariate drift results for the requested window.",
    )
    async def feature_drift(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> FeatureDriftResponse:
        return await service.feature_drift(session.deployment_id, dims)

    @router.get(
        "/output-drift",
        response_model=OutputDriftResponse,
        summary="Get dashboard output-drift metrics",
        description="Return model-output drift results for the requested window.",
    )
    async def output_drift(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> OutputDriftResponse:
        return await service.output_drift(session.deployment_id, dims)

    @router.get(
        "/reference-profile",
        response_model=ReferenceProfileResponse,
        summary="Get the dashboard reference profile",
        description="Return the reference-profile summary used by monitoring metrics.",
    )
    async def reference_profile(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> ReferenceProfileResponse:
        return await service.reference_profile(session.deployment_id, dims)

    @router.get(
        "/alerts",
        response_model=AlertsResponse,
        summary="List dashboard monitoring alerts",
        description="Return monitoring alerts for the requested window.",
    )
    async def alerts(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> AlertsResponse:
        return await service.alerts(session.deployment_id, dims)

    @router.post(
        "/alerts/acknowledge",
        response_model=AlertsResponse,
        summary="Acknowledge a monitoring alert",
        description="Mark an alert as seen and return the updated alerts for the requested window.",
    )
    async def acknowledge_alert(
        body: AcknowledgeAlertRequest,
        session: MonitoringSession = Depends(require_monitoring_write),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> AlertsResponse:
        return await service.acknowledge_alert(session.deployment_id, body.metric, dims)

    @router.get(
        "/worker",
        response_model=WorkerHealthResponse,
        summary="Get dashboard monitoring worker health",
        description="Report whether monitoring is processing this deployment on schedule.",
    )
    async def worker_health(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> WorkerHealthResponse:
        return await service.worker_health(session.deployment_id)

    @router.get(
        "/traces",
        response_model=TracesResponse,
        summary="List dashboard inference traces",
        description="Return a page of inference traces for the requested window.",
    )
    async def traces(
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        limit: int = Query(TRACES_DEFAULT_LIMIT, ge=1, le=TRACES_MAX_LIMIT),
        offset: int = Query(0, ge=0),
        sort: TraceSort = TraceSort.TS,
        order: SortOrder = SortOrder.DESC,
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> TracesResponse:
        return await service.traces(
            session.deployment_id, dims, limit=limit, offset=offset, sort=sort, order=order
        )

    @router.get(
        "/traces/{event_id}",
        response_model=TraceDetailResponse,
        summary="Get a dashboard inference trace",
        description="Return one inference trace from the requested window.",
    )
    async def trace_detail(
        event_id: str,
        session: MonitoringSession = Depends(require_monitoring_session),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> TraceDetailResponse:
        detail = await service.trace_detail(session.deployment_id, dims, event_id)
        if detail.state is SectionState.EMPTY:
            raise HTTPException(status_code=404, detail="trace not found in this window")
        return detail

    return router


HostedFn = Callable[[UUID], bool | Awaitable[bool]]


def build_machine_router(hosted: HostedFn) -> APIRouter:
    """Monitoring as a facet of the deployment tree — the machine surface.

    Addressed by deployment because the caller's credential does not carry one: a bearer
    key is valid for a whole orbit, so the request itself must say which deployment it is
    about. Authentication is attached where the router is included, alongside the rest of
    the deployment tree, so this surface and inference share one credential story.

    Read-only by construction: acknowledging alerts stays on the session surface — the
    machines watch, a person decides.
    """
    router = APIRouter(prefix="/deployments/{deployment_id}/monitoring", tags=[MONITORING_FACET])

    async def _hosted_deployment(deployment_id: UUID) -> UUID:
        result = hosted(deployment_id)
        is_hosted = await result if inspect.isawaitable(result) else result
        if not is_hosted:
            raise DeploymentNotHostedError()
        return deployment_id

    @router.get(
        "/header",
        response_model=HeaderResponse,
        summary="Get the monitoring header",
        description="Return deployment identity, model kind, and reference-profile state.",
    )
    async def header(
        deployment_id: UUID = Depends(_hosted_deployment),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> HeaderResponse:
        return await service.header(deployment_id)

    @router.get(
        "/overview",
        response_model=OverviewResponse,
        summary="Get the monitoring overview",
        description="Return a summary of monitoring results for the requested window.",
    )
    async def overview(
        deployment_id: UUID = Depends(_hosted_deployment),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> OverviewResponse:
        return await service.overview(deployment_id, dims)

    @router.get(
        "/runtime",
        response_model=RuntimeResponse,
        summary="Get runtime metrics",
        description="Return request volume, latency, and error metrics for the requested window.",
    )
    async def runtime(
        deployment_id: UUID = Depends(_hosted_deployment),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> RuntimeResponse:
        return await service.runtime(deployment_id, dims)

    @router.get(
        "/data-quality",
        response_model=DataQualityResponse,
        summary="Get data-quality metrics",
        description="Return input data-quality checks for the requested window.",
    )
    async def data_quality(
        deployment_id: UUID = Depends(_hosted_deployment),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> DataQualityResponse:
        return await service.data_quality(deployment_id, dims)

    @router.get(
        "/feature-drift",
        response_model=FeatureDriftResponse,
        summary="Get feature-drift metrics",
        description="Return feature and multivariate drift results for the requested window.",
    )
    async def feature_drift(
        deployment_id: UUID = Depends(_hosted_deployment),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> FeatureDriftResponse:
        return await service.feature_drift(deployment_id, dims)

    @router.get(
        "/output-drift",
        response_model=OutputDriftResponse,
        summary="Get output-drift metrics",
        description="Return model-output drift results for the requested window.",
    )
    async def output_drift(
        deployment_id: UUID = Depends(_hosted_deployment),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> OutputDriftResponse:
        return await service.output_drift(deployment_id, dims)

    @router.get(
        "/reference-profile",
        response_model=ReferenceProfileResponse,
        summary="Get the reference profile",
        description="Return the reference-profile summary used by monitoring metrics.",
    )
    async def reference_profile(
        deployment_id: UUID = Depends(_hosted_deployment),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> ReferenceProfileResponse:
        return await service.reference_profile(deployment_id, dims)

    @router.get(
        "/alerts",
        response_model=AlertsResponse,
        summary="List monitoring alerts",
        description="Return monitoring alerts for the requested window.",
    )
    async def alerts(
        deployment_id: UUID = Depends(_hosted_deployment),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> AlertsResponse:
        return await service.alerts(deployment_id, dims)

    @router.get(
        "/traces",
        response_model=TracesResponse,
        summary="List inference traces",
        description="Return a page of inference traces for the requested window.",
    )
    async def traces(
        deployment_id: UUID = Depends(_hosted_deployment),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        limit: int = Query(TRACES_DEFAULT_LIMIT, ge=1, le=TRACES_MAX_LIMIT),
        offset: int = Query(0, ge=0),
        sort: TraceSort = TraceSort.TS,
        order: SortOrder = SortOrder.DESC,
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> TracesResponse:
        return await service.traces(
            deployment_id, dims, limit=limit, offset=offset, sort=sort, order=order
        )

    @router.get(
        "/traces/{event_id}",
        response_model=TraceDetailResponse,
        summary="Get an inference trace",
        description="Return one inference trace from the requested window.",
    )
    async def trace_detail(
        event_id: str,
        deployment_id: UUID = Depends(_hosted_deployment),  # noqa: B008
        dims: QueryDimensions = Depends(_dimensions),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> TraceDetailResponse:
        detail = await service.trace_detail(deployment_id, dims, event_id)
        if detail.state is SectionState.EMPTY:
            raise HTTPException(status_code=404, detail="trace not found in this window")
        return detail

    @router.get(
        "/worker",
        response_model=WorkerHealthResponse,
        summary="Get monitoring worker health",
        description="Report whether monitoring is processing this deployment on schedule.",
    )
    async def worker(
        deployment_id: UUID = Depends(_hosted_deployment),  # noqa: B008
        service: MonitoringQueryService = Depends(get_query_service),  # noqa: B008
    ) -> WorkerHealthResponse:
        """Whether monitoring itself is keeping up — not a metric about the model."""
        return await service.worker_health(deployment_id)

    return router
