import re
from collections.abc import Mapping
from typing import Never
from uuid import UUID

from fastapi import status

from luml.handlers.api_keys import APIKeyHandler
from luml.handlers.permissions import PermissionsHandler
from luml.infra.db import engine
from luml.infra.exceptions import (
    ApplicationError,
    ArtifactStatusMismatchError,
    InsufficientPermissionsError,
    NotFoundError,
)
from luml.repositories.artifacts import ArtifactRepository
from luml.repositories.bucket_secrets import BucketSecretRepository
from luml.repositories.collections import CollectionRepository
from luml.repositories.deployments import DeploymentRepository
from luml.repositories.orbits import OrbitRepository
from luml.repositories.satellites import SatelliteRepository
from luml.repositories.users import UserRepository
from luml.schemas.artifacts import Artifact
from luml.schemas.deployment import (
    Deployment,
    DeploymentCreate,
    DeploymentCreateIn,
    DeploymentDetailsUpdate,
    DeploymentDetailsUpdateIn,
    DeploymentStatus,
    DeploymentUpdate,
    DeploymentUpdateIn,
    MonitoringMode,
)
from luml.schemas.permissions import Action, Resource
from luml.schemas.satellite import (
    DEPLOY_CAPABILITY,
    MONITORING_CAPABILITY,
    DeployCapabilityV1,
    Satellite,
    SatelliteQueueTask,
)

_MISSING = object()
_KNOWN_VALIDATORS = frozenset({"min", "max", "regex", "equal", "in", "notEqual"})


def _strict_equal(left: object, right: object) -> bool:
    if (
        isinstance(left, int | float)
        and not isinstance(left, bool)
        and isinstance(right, int | float)
        and not isinstance(right, bool)
    ):
        return left == right
    return type(left) is type(right) and left == right


def _field_condition_holds(
    body: Mapping[str, object], current_values: Mapping[str, object]
) -> bool:
    field = body.get("field")
    operator = body.get("operator")
    if not isinstance(field, str) or not isinstance(operator, str):
        return False

    if operator == "includes":
        return field in current_values
    if operator == "notIncludes":
        return field not in current_values

    current = current_values.get(field, _MISSING)
    expected = body.get("value")
    if operator == "equal":
        return _strict_equal(current, expected)
    if operator == "notEqual":
        return not _strict_equal(current, expected)
    if not (
        isinstance(current, int | float)
        and not isinstance(current, bool)
        and isinstance(expected, int | float)
        and not isinstance(expected, bool)
    ):
        return False
    comparisons = {
        "gt": current > expected,
        "gte": current >= expected,
        "lt": current < expected,
        "lte": current <= expected,
    }
    return comparisons.get(operator, False)


def _tag_condition_holds(
    operator: str, expected: object, producer_tags: list[str]
) -> bool:
    if not isinstance(expected, list):
        return True
    combinations = [
        (
            isinstance(combination, list),
            isinstance(combination, list)
            and all(tag in producer_tags for tag in combination),
        )
        for combination in expected
    ]
    if operator == "includes":
        return any(valid and matches for valid, matches in combinations)
    if operator == "notIncludes":
        return all(valid and not matches for valid, matches in combinations)
    return False


def _variant_condition_holds(operator: str, expected: object, variant: str) -> bool:
    if operator == "eq":
        return _strict_equal(variant, expected)
    if operator == "neq":
        return not _strict_equal(variant, expected)
    if operator == "includes":
        return isinstance(expected, str) and variant in expected
    if operator == "notIncludes":
        return isinstance(expected, str) and variant not in expected
    return False


def _model_condition_holds(
    body: Mapping[str, object],
    producer_tags: list[str],
    version: str,
    variant: str,
) -> bool:
    field = body.get("field")
    operator = body.get("operator")
    expected = body.get("value")
    if not isinstance(field, str) or not isinstance(operator, str):
        return False

    if field == "tags":
        return _tag_condition_holds(operator, expected, producer_tags)
    if field == "version":
        if operator == "eq":
            return _strict_equal(version, expected)
        if operator == "neq":
            return not _strict_equal(version, expected)
        return False
    if field == "variant":
        return _variant_condition_holds(operator, expected, variant)
    return False


def _condition_holds(
    condition: object,
    current_values: Mapping[str, object],
    producer_tags: list[str],
    version: str,
    variant: str,
) -> bool:
    if not isinstance(condition, Mapping):
        return True
    body = condition.get("body")
    if isinstance(body, list):
        return satellite_field_conditions_hold(
            body,
            current_values,
            producer_tags=producer_tags,
            version=version,
            variant=variant,
        )

    condition_type = condition.get("type")
    if not isinstance(condition_type, str) or condition_type not in {
        "field",
        "model",
    }:
        return True
    if not isinstance(body, Mapping):
        return False
    if condition_type == "field":
        return _field_condition_holds(body, current_values)
    return _model_condition_holds(body, producer_tags, version, variant)


def satellite_field_conditions_hold(
    conditions: object,
    current_values: Mapping[str, object],
    *,
    producer_tags: list[str],
    version: str | None,
    variant: str | None,
) -> bool:
    if not isinstance(conditions, list):
        return True
    return all(
        _condition_holds(
            condition,
            current_values,
            producer_tags,
            version or "",
            variant or "",
        )
        for condition in conditions
    )


def _field_type_accepts(field: Mapping[str, object], value: object) -> bool | None:
    field_type = field.get("type")
    if field_type == "boolean":
        return type(value) is bool
    if field_type == "number":
        return type(value) is int
    if field_type == "text":
        return type(value) is str
    if field_type != "dropdown":
        return None

    options = field.get("values")
    if not isinstance(options, list):
        return False
    return any(
        isinstance(option, Mapping)
        and _strict_equal(value, option.get("value", _MISSING))
        for option in options
    )


def _validator_accepts(value: object, validator: object) -> bool | None:
    if not isinstance(validator, Mapping):
        return None
    validator_type = validator.get("type")
    if not isinstance(validator_type, str) or validator_type not in _KNOWN_VALIDATORS:
        return None
    expected = validator.get("value")
    try:
        if validator_type == "min":
            return (
                isinstance(value, int | float)
                and not isinstance(value, bool)
                and isinstance(expected, int | float)
                and not isinstance(expected, bool)
                and value >= expected
            )
        if validator_type == "max":
            return (
                isinstance(value, int | float)
                and not isinstance(value, bool)
                and isinstance(expected, int | float)
                and not isinstance(expected, bool)
                and value <= expected
            )
        if validator_type == "regex":
            return (
                isinstance(value, str)
                and isinstance(expected, str)
                and re.search(expected, value) is not None
            )
        if validator_type == "equal":
            return _strict_equal(value, expected)
        if validator_type == "notEqual":
            return not _strict_equal(value, expected)
        if validator_type == "in":
            return isinstance(expected, list) and any(
                _strict_equal(value, item) for item in expected
            )
    except re.error:
        return False
    return False


def _parameter_error(field: str, rule: str) -> Never:
    raise ApplicationError(
        f"Invalid satellite parameter '{field}': failed {rule}",
        status.HTTP_422_UNPROCESSABLE_CONTENT,
    )


def validate_satellite_parameters(
    deploy: DeployCapabilityV1,
    parameters: Mapping[str, object],
    artifact: Artifact,
) -> None:
    for field in deploy.extra_fields_form_spec:
        name = field.get("name")
        if not isinstance(name, str):
            continue
        offered = satellite_field_conditions_hold(
            field.get("conditions", []),
            parameters,
            producer_tags=artifact.manifest.producer_tags,
            version=artifact.manifest.version,
            variant=artifact.manifest.variant,
        )
        present = name in parameters
        if present and not offered:
            _parameter_error(name, "condition")
        if field.get("required") is True and offered and not present:
            _parameter_error(name, "required rule")
        if not present:
            continue

        value = parameters[name]
        type_result = _field_type_accepts(field, value)
        if type_result is False:
            _parameter_error(name, f"type '{field.get('type')}'")

        validators = field.get("validators", [])
        if not isinstance(validators, list):
            continue
        for validator in validators:
            result = _validator_accepts(value, validator)
            if result is False:
                validator_type = (
                    validator.get("type")
                    if isinstance(validator, Mapping)
                    else "validator"
                )
                _parameter_error(name, f"validator '{validator_type}'")


class DeploymentHandler:
    __repo = DeploymentRepository(engine)
    __sat_repo = SatelliteRepository(engine)
    __orbit_repo = OrbitRepository(engine)
    __artifact_repo = ArtifactRepository(engine)
    __collection_repo = CollectionRepository(engine)
    __secret_repo = BucketSecretRepository(engine)
    __user_repo = UserRepository(engine)
    __permissions_handler = PermissionsHandler()
    __api_key_handler = APIKeyHandler()

    @staticmethod
    def _convert_dynamic_attributes_secrets(
        dynamic_attributes: dict[str, UUID],
    ) -> dict[str, str]:
        return {k: str(v) for k, v in (dynamic_attributes or {}).items()}

    @staticmethod
    def _require_present_capability(
        satellite: Satellite,
        capability: str,
    ) -> None:
        if capability not in satellite.present_capabilities:
            raise ApplicationError(
                f"Satellite does not have a present '{capability}' capability",
                status.HTTP_409_CONFLICT,
            )

    @classmethod
    def _validate_create_capabilities(
        cls,
        satellite: Satellite,
        artifact: Artifact,
        monitoring_mode: MonitoringMode,
        satellite_parameters: Mapping[str, object],
    ) -> None:
        cls._require_present_capability(satellite, DEPLOY_CAPABILITY)
        deploy = DeployCapabilityV1.model_validate(
            satellite.capabilities[DEPLOY_CAPABILITY]
        )
        if artifact.manifest.variant not in deploy.supported_variants:
            raise ApplicationError(
                f"Artifact variant '{artifact.manifest.variant}' is not in deploy "
                "supported_variants",
                status.HTTP_409_CONFLICT,
            )

        tag_combinations = deploy.supported_tags_combinations
        producer_tags = set(artifact.manifest.producer_tags)
        if tag_combinations is not None and not any(
            all(tag in producer_tags for tag in combination)
            for combination in tag_combinations
        ):
            raise ApplicationError(
                "Artifact producer tags do not satisfy deploy "
                "supported_tags_combinations",
                status.HTTP_409_CONFLICT,
            )

        validate_satellite_parameters(deploy, satellite_parameters, artifact)

        if monitoring_mode != MonitoringMode.OFF:
            cls._require_present_capability(satellite, MONITORING_CAPABILITY)

    async def create_deployment(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        data: DeploymentCreateIn,
    ) -> Deployment:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.DEPLOYMENT,
            Action.CREATE,
            orbit_id,
        )

        orbit = await self.__orbit_repo.get_orbit_simple(orbit_id, organization_id)
        if not orbit:
            raise NotFoundError("Orbit not found")

        satellite = await self.__sat_repo.get_satellite(data.satellite_id)
        if not satellite or satellite.orbit_id != orbit_id:
            raise NotFoundError("Satellite not found")

        artifact = await self.__artifact_repo.get_artifact(data.artifact_id)
        if not artifact:
            raise NotFoundError("Artifact not found")

        collection = await self.__collection_repo.get_collection(artifact.collection_id)
        if not collection or collection.orbit_id != orbit_id:
            raise NotFoundError("Collection not found")

        user = await self.__user_repo.get_public_user_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")

        self._validate_create_capabilities(
            satellite,
            artifact,
            data.monitoring_mode,
            data.satellite_parameters,
        )

        try:
            deployment, _ = await self.__repo.create_deployment(
                DeploymentCreate(
                    orbit_id=orbit_id,
                    satellite_id=data.satellite_id,
                    artifact_id=data.artifact_id,
                    name=data.name,
                    monitoring_mode=data.monitoring_mode,
                    satellite_parameters=data.satellite_parameters,
                    description=data.description,
                    dynamic_attributes_secrets=self._convert_dynamic_attributes_secrets(
                        data.dynamic_attributes_secrets
                    ),
                    env_variables_secrets=self._convert_dynamic_attributes_secrets(
                        data.env_variables_secrets
                    ),
                    env_variables=data.env_variables,
                    created_by_user=user.full_name,
                    tags=data.tags,
                )
            )
        except ArtifactStatusMismatchError as error:
            raise ApplicationError(error.message, status.HTTP_409_CONFLICT) from error
        return deployment

    async def list_deployments(
        self, user_id: UUID, organization_id: UUID, orbit_id: UUID
    ) -> list[Deployment]:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.DEPLOYMENT,
            Action.LIST,
            orbit_id,
        )
        return await self.__repo.list_deployments(orbit_id)

    async def get_deployment(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        deployment_id: UUID,
    ) -> Deployment:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.DEPLOYMENT,
            Action.READ,
            orbit_id,
        )
        deployment = await self.__repo.get_deployment(deployment_id, orbit_id)
        if not deployment:
            raise NotFoundError("Deployment not found")
        return deployment

    async def request_deployment_deletion(
        self, user_id: UUID, organization_id: UUID, orbit_id: UUID, deployment_id: UUID
    ) -> SatelliteQueueTask:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.DEPLOYMENT,
            Action.DELETE,
            orbit_id,
        )
        result = await self.__repo.request_deployment_deletion(orbit_id, deployment_id)

        if not result:
            raise NotFoundError("Deployment not found")

        deployment, task = result

        if task is None:
            raise ApplicationError(
                "Deployment deletion already pending",
                409,
            )

        return task

    async def force_delete_deployment(
        self, user_id: UUID, organization_id: UUID, orbit_id: UUID, deployment_id: UUID
    ) -> None:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.DEPLOYMENT,
            Action.DELETE,
            orbit_id,
        )
        dep = await self.__repo.get_deployment(deployment_id, orbit_id)

        if not dep:
            raise NotFoundError("Deployment not found")

        return await self.__repo.delete_deployment(deployment_id, orbit_id)

    async def list_worker_deployments(self, satellite_id: UUID) -> list[Deployment]:
        return await self.__repo.list_satellite_deployments(satellite_id)

    async def get_worker_deployment(
        self, satellite_id: UUID, deployment_id: UUID
    ) -> Deployment:
        deployment = await self.__repo.get_satellite_deployment(
            deployment_id, satellite_id
        )
        if not deployment:
            raise NotFoundError("Deployment not found")
        return deployment

    async def update_worker_deployment(
        self,
        satellite_id: UUID,
        deployment_id: UUID,
        data: DeploymentUpdateIn,
    ) -> Deployment:
        update_data = DeploymentUpdate.model_validate(
            {"id": deployment_id, **data.model_dump(exclude_unset=True)}
        )
        deployment = await self.__repo.update_deployment(
            deployment_id,
            satellite_id,
            update_data,
        )
        if not deployment:
            raise NotFoundError("Deployment not found")
        return deployment

    async def delete_worker_deployment(
        self, satellite_id: UUID, deployment_id: UUID
    ) -> None:
        deployment = await self.__repo.get_satellite_deployment(
            deployment_id, satellite_id
        )
        if not deployment:
            raise NotFoundError("Deployment not found")
        if deployment.status != DeploymentStatus.DELETION_PENDING:
            raise ApplicationError(
                "Incorrect deployment status. Request deployment deletion first.",
                409,
            )
        return await self.__repo.delete_satellite_deployment(
            deployment_id, satellite_id
        )

    async def update_deployment_details(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        deployment_id: UUID,
        data: DeploymentDetailsUpdateIn,
    ) -> Deployment:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.DEPLOYMENT,
            Action.UPDATE,
            orbit_id,
        )
        if (
            data.monitoring_mode is not None
            and data.monitoring_mode != MonitoringMode.OFF
        ):
            deployment = await self.__repo.get_deployment(deployment_id, orbit_id)
            if not deployment:
                raise NotFoundError("Deployment not found")
            if data.monitoring_mode != deployment.monitoring_mode:
                satellite = await self.__sat_repo.get_satellite(deployment.satellite_id)
                if not satellite:
                    raise NotFoundError("Satellite not found")
                self._require_present_capability(
                    satellite,
                    MONITORING_CAPABILITY,
                )

        updated = await self.__repo.update_deployment_details(
            orbit_id,
            deployment_id,
            DeploymentDetailsUpdate.model_validate(
                data.model_dump(mode="json", exclude_unset=True)
            ),
        )
        if not updated:
            raise NotFoundError("Deployment not found")
        return updated

    async def verify_user_inference_access(self, orbit_id: UUID, api_key: str) -> bool:
        user = await self.__api_key_handler.authenticate_api_key(api_key)
        if not user:
            return False
        orbit = await self.__orbit_repo.get_orbit_by_id(orbit_id)
        if not orbit:
            return False
        try:
            await self.__permissions_handler.check_permissions(
                orbit.organization_id,
                user.id,
                Resource.DEPLOYMENT,
                Action.READ,
                orbit.id,
            )
        except (NotFoundError, InsufficientPermissionsError):
            return False
        return True

    async def update_worker_deployment_status(
        self,
        satellite_id: UUID,
        deployment_id: UUID,
        status: DeploymentStatus,
    ) -> Deployment:
        deployment = await self.__repo.update_deployment(
            deployment_id,
            satellite_id,
            DeploymentUpdate(id=deployment_id, status=status),
        )
        if not deployment:
            raise NotFoundError("Deployment not found")
        return deployment
