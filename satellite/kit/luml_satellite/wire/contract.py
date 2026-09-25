import logging
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from luml_satellite._version import SATELLITE_API_VERSION
from luml_satellite.wire.pairing import SatelliteContract

_PATH_PARAMETER = re.compile(r"\{[^{}\/]+\}")
_HTTP_METHODS = frozenset({"delete", "get", "head", "options", "patch", "post", "put"})


@dataclass(frozen=True, order=True)
class ContractOperation:
    method: str
    path: str

    @property
    def label(self) -> str:
        return f"{self.method.upper()} {self.path}"


CLIENT_OPERATIONS = frozenset(
    {
        ContractOperation("post", "/satellites/v1/pair"),
        ContractOperation("get", "/satellites/v1/contract"),
        ContractOperation("get", "/satellites/v1/secrets"),
        ContractOperation("get", "/satellites/v1/secrets/{secret_id}"),
        ContractOperation("get", "/satellites/v1/tasks"),
        ContractOperation("post", "/satellites/v1/tasks/{task_id}/status"),
        ContractOperation("get", "/satellites/v1/deployments"),
        ContractOperation("get", "/satellites/v1/deployments/{deployment_id}"),
        ContractOperation("patch", "/satellites/v1/deployments/{deployment_id}"),
        ContractOperation("patch", "/satellites/v1/deployments/{deployment_id}/status"),
        ContractOperation("delete", "/satellites/v1/deployments/{deployment_id}"),
        ContractOperation("post", "/satellites/v1/deployments/inference-access"),
        ContractOperation("post", "/satellites/v1/monitoring/introspect"),
        ContractOperation("get", "/satellites/v1/artifacts/{artifact_id}/download-url"),
        ContractOperation("get", "/satellites/v1/artifacts/{artifact_id}"),
    }
)


class ContractVerdict(StrEnum):
    OK = "ok"
    UNAVAILABLE = "unavailable"
    PLATFORM_OLDER = "older_platform"
    PLATFORM_NEWER = "newer_platform"


@dataclass(frozen=True)
class ContractComparison:
    verdict: ContractVerdict
    client_api_version: int = SATELLITE_API_VERSION
    platform_api_version: int | None = None
    missing_operations: tuple[ContractOperation, ...] = ()
    detail: str | None = None

    @classmethod
    def unavailable(cls, detail: str) -> ContractComparison:
        return cls(verdict=ContractVerdict.UNAVAILABLE, detail=detail)


def normalize_contract_path(path: str) -> str:
    normalized = _PATH_PARAMETER.sub("{}", path.rstrip("/"))
    return normalized or "/"


def contract_operations(openapi: Mapping[str, Any]) -> frozenset[ContractOperation]:
    paths = openapi.get("paths")
    if not isinstance(paths, Mapping):
        return frozenset()

    operations: set[ContractOperation] = set()
    for path, path_item in paths.items():
        if not isinstance(path, str) or not isinstance(path_item, Mapping):
            continue
        for method in path_item:
            normalized_method = str(method).lower()
            if normalized_method in _HTTP_METHODS:
                operations.add(ContractOperation(normalized_method, normalize_contract_path(path)))
    return frozenset(operations)


def compare_contract(
    contract: SatelliteContract,
    *,
    required_operations: Iterable[ContractOperation] = CLIENT_OPERATIONS,
    client_api_version: int = SATELLITE_API_VERSION,
) -> ContractComparison:
    available = {
        ContractOperation(operation.method, normalize_contract_path(operation.path))
        for operation in contract_operations(contract.openapi)
    }
    required = {
        ContractOperation(operation.method.lower(), normalize_contract_path(operation.path))
        for operation in required_operations
    }
    missing = tuple(sorted(required - available))
    if missing or contract.api_version < client_api_version:
        return ContractComparison(
            verdict=ContractVerdict.PLATFORM_OLDER,
            client_api_version=client_api_version,
            platform_api_version=contract.api_version,
            missing_operations=missing,
        )
    if contract.api_version > client_api_version:
        return ContractComparison(
            verdict=ContractVerdict.PLATFORM_NEWER,
            client_api_version=client_api_version,
            platform_api_version=contract.api_version,
        )
    return ContractComparison(
        verdict=ContractVerdict.OK,
        client_api_version=client_api_version,
        platform_api_version=contract.api_version,
    )


def log_contract_comparison(
    comparison: ContractComparison,
    logger: logging.Logger,
) -> None:
    if comparison.verdict is ContractVerdict.UNAVAILABLE:
        logger.warning("satellite contract unavailable: %s", comparison.detail)
    elif comparison.verdict is ContractVerdict.PLATFORM_OLDER:
        missing = ", ".join(operation.label for operation in comparison.missing_operations)
        suffix = f"; missing operations: {missing}" if missing else ""
        logger.error(
            "platform satellite contract is older (platform API %s, kit API %s)%s",
            comparison.platform_api_version,
            comparison.client_api_version,
            suffix,
        )
    elif comparison.verdict is ContractVerdict.PLATFORM_NEWER:
        logger.warning(
            "platform satellite contract is newer (platform API %s, kit API %s)",
            comparison.platform_api_version,
            comparison.client_api_version,
        )
    else:
        logger.info("platform satellite contract is compatible")
