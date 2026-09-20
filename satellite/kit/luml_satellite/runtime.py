import logging
import random
from collections.abc import Awaitable, Callable, Mapping
from contextlib import suppress
from typing import Protocol, runtime_checkable

from luml_satellite.convergence import (
    Convergence,
    CustomTaskHandler,
    MonitoringLinks,
    NoServingPlacement,
    PollingPass,
    Reconciliation,
    ServingPlacement,
)
from luml_satellite.declaration import (
    CapabilityDeclaration,
    MonitoringBundleCapabilities,
    SatelliteConfiguration,
    derive_capabilities,
    pair_satellite,
)
from luml_satellite.tokens import TokenDeriver
from luml_satellite.wire import AuthenticationFailure, PlatformClient
from luml_satellite.workload import (
    ArtifactResolver,
    Clock,
    RecordingPolicy,
    SystemClock,
    WorkloadDriver,
)

_AUTHENTICATION_MESSAGE = "platform rejected the satellite token; re-pair this satellite"


class RuntimeMonitoringBundle(MonitoringBundleCapabilities, MonitoringLinks, Protocol):
    pass


@runtime_checkable
class RuntimeStartable(Protocol):
    def start(self) -> Awaitable[None]: ...


@runtime_checkable
class RuntimeCloseable(Protocol):
    def aclose(self) -> Awaitable[None]: ...


@runtime_checkable
class ReconciliationAware(Protocol):
    def mark_reconciled(self) -> None: ...


@runtime_checkable
class InternalApplicationProvider(Protocol):
    @property
    def internal_application(self) -> object | None: ...


@runtime_checkable
class OpenAPIProvider(Protocol):
    def openapi(self) -> Mapping[str, object]: ...


class SatelliteRuntime:
    def __init__(
        self,
        configuration: SatelliteConfiguration,
        platform: PlatformClient,
        driver: WorkloadDriver,
        *,
        serving: ServingPlacement | None = None,
        monitoring: RuntimeMonitoringBundle | None = None,
        artifact_resolver: ArtifactResolver | None = None,
        custom_handlers: Mapping[str, CustomTaskHandler] | None = None,
        public_application: object | None = None,
        internal_application: object | None = None,
        pairing_document: Callable[[], Mapping[str, object]] | None = None,
        slug: str | None = None,
        serves_deployments: bool | None = None,
        clock: Clock | None = None,
        jitter: Callable[[float], float] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        if configuration.POLL_INTERVAL_SEC <= 0:
            raise ValueError("POLL_INTERVAL_SEC must be greater than zero")

        self.configuration = configuration
        self.platform = platform
        self.driver = driver
        self.serving = serving or NoServingPlacement()
        self.monitoring = monitoring if configuration.MONITORING_ENABLED else None
        self.clock = clock or SystemClock()
        self.jitter = jitter or _full_jitter
        self.logger = logger or logging.getLogger("luml_satellite.runtime")
        self.slug = slug
        self._pairing_document = pairing_document
        self._public_application = (
            public_application if public_application is not None else self.serving.router
        )
        self._internal_application = (
            internal_application
            if internal_application is not None
            else (
                self.serving.internal_application
                if isinstance(self.serving, InternalApplicationProvider)
                else None
            )
        )
        self._serves_deployments = (
            self._public_application is not None
            if serves_deployments is None
            else serves_deployments
        )
        self._stopped = False

        resolver = artifact_resolver or ArtifactResolver(
            platform,
            TokenDeriver(configuration.DERIVATION_KEY or configuration.SATELLITE_TOKEN),
            satellite_address=configuration.BASE_URL,
        )
        recording_policy = RecordingPolicy(
            sample_rate=configuration.RECORDING_SAMPLE_RATE,
            body_max_bytes=configuration.RECORDING_BODY_MAX_BYTES,
            keep_inputs=configuration.RECORDING_KEEP_INPUTS,
            keep_outputs=configuration.RECORDING_KEEP_OUTPUTS,
        )
        self.convergence = Convergence(
            platform,
            driver,
            resolver,
            serving=self.serving,
            monitoring=self.monitoring,
            clock=self.clock,
            max_parallel=configuration.MAX_PARALLEL_CONVERGENCE,
            max_relaunch_attempts=configuration.MAX_RELAUNCH_ATTEMPTS,
            driver_call_timeout=configuration.DRIVER_CALL_TIMEOUT_SEC,
            default_health_check_timeout=configuration.HEALTH_CHECK_TIMEOUT_SEC,
            telemetry_endpoint=configuration.OTEL_EXPORTER_OTLP_ENDPOINT,
            recording_policy=recording_policy,
            logger=self.logger,
        )
        self.polling = PollingPass(
            platform,
            self.convergence,
            custom_handlers=custom_handlers,
            logger=self.logger,
        )
        self.reconciliation = Reconciliation(
            platform,
            self.convergence,
            self.polling,
            clock=self.clock,
            backoff_base=configuration.POLL_INTERVAL_SEC,
            backoff_cap=configuration.POLL_BACKOFF_MAX_SEC,
            jitter=self.jitter,
            logger=self.logger,
        )

    @property
    def capabilities(self) -> CapabilityDeclaration:
        return derive_capabilities(
            supported_variants=self.driver.supported_variants,
            supported_tags_combinations=self.driver.supported_tag_combinations,
            settings_type=self.driver.settings_type,
            monitoring_bundle=self.monitoring,
            serves_deployments=self._serves_deployments,
        )

    @property
    def public_application(self) -> object | None:
        return self._public_application

    @property
    def internal_application(self) -> object | None:
        return self._internal_application

    async def pair(self) -> None:
        await pair_satellite(
            self.platform,
            kind=self.driver.kind,
            capabilities=self.capabilities,
            base_url=self.configuration.BASE_URL,
            slug=self.slug,
            openapi=self._openapi_document(),
            logger=self.logger,
        )

    async def reconcile(self) -> None:
        await self.reconciliation.run()
        self._mark_reconciled()

    async def poll(self) -> None:
        await self.polling.run()

    async def health_pass(self) -> None:
        await self.convergence.health_pass()

    def stop(self) -> None:
        self._stopped = True

    async def run_forever(self) -> None:
        self._stopped = False
        try:
            await self._start_monitoring()
            await self._pair_with_backoff()
            if self._stopped:
                return
            await self.reconcile()
            self._mark_reconciled()
            next_health = self.clock.monotonic() + self.configuration.HEALTH_PASS_INTERVAL_SEC
            failures = 0
            while not self._stopped:
                try:
                    await self.poll()
                    if (
                        self.configuration.HEALTH_PASS_INTERVAL_SEC > 0
                        and self.clock.monotonic() >= next_health
                    ):
                        await self.health_pass()
                        next_health = (
                            self.clock.monotonic() + self.configuration.HEALTH_PASS_INTERVAL_SEC
                        )
                except Exception as error:
                    failures += 1
                    self._log_loop_failure(error, failures)
                    if self._stopped:
                        break
                    await self.clock.sleep(self._backoff_delay(failures))
                    continue

                failures = 0
                if self._stopped:
                    break
                await self.clock.sleep(self.configuration.POLL_INTERVAL_SEC)
        finally:
            await self.polling.drain()
            await self._close_serving()
            await self._close_monitoring()

    async def _pair_with_backoff(self) -> None:
        failures = 0
        while not self._stopped:
            try:
                await self.pair()
                return
            except Exception as error:
                failures += 1
                if isinstance(error, AuthenticationFailure):
                    self.logger.warning(_AUTHENTICATION_MESSAGE)
                else:
                    self.logger.warning("satellite pairing failed: %s", error)
                await self.clock.sleep(self._backoff_delay(failures))

    def _openapi_document(self) -> dict[str, object] | None:
        if self._pairing_document is not None:
            return dict(self._pairing_document())
        if isinstance(self._public_application, OpenAPIProvider):
            return dict(self._public_application.openapi())
        return None

    def _backoff_delay(self, failures: int) -> float:
        exponent = min(max(failures - 1, 0), 62)
        ceiling = min(
            self.configuration.POLL_BACKOFF_MAX_SEC,
            self.configuration.POLL_INTERVAL_SEC * (2**exponent),
        )
        return float(max(0.0, min(ceiling, self.jitter(ceiling))))

    def _log_loop_failure(self, error: Exception, failures: int) -> None:
        if isinstance(error, AuthenticationFailure):
            self.logger.warning(_AUTHENTICATION_MESSAGE)
        else:
            self.logger.warning("satellite loop pass failed: %s", error)
        if failures == 5:
            self.logger.error(
                "satellite loop failed five consecutive times; last error: %s",
                error,
            )

    async def _start_monitoring(self) -> None:
        if isinstance(self.monitoring, RuntimeStartable):
            await self.monitoring.start()

    async def _close_monitoring(self) -> None:
        if isinstance(self.monitoring, RuntimeCloseable):
            with suppress(Exception):
                await self.monitoring.aclose()

    def _mark_reconciled(self) -> None:
        if isinstance(self.serving, ReconciliationAware):
            self.serving.mark_reconciled()

    async def _close_serving(self) -> None:
        if isinstance(self.serving, RuntimeCloseable):
            with suppress(Exception):
                await self.serving.aclose()


Runtime = SatelliteRuntime


def _full_jitter(ceiling: float) -> float:
    return random.uniform(0.0, ceiling)
