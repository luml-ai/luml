import time
import uuid
from typing import Any
from uuid import UUID

import jwt
from fastapi import status
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError

from luml.handlers.permissions import PermissionsHandler
from luml.infra.db import engine
from luml.infra.exceptions import ApplicationError, NotFoundError
from luml.repositories.deployments import DeploymentRepository
from luml.repositories.monitoring import MonitoringLaunchTokenRepository
from luml.repositories.satellites import SatelliteRepository
from luml.schemas.deployment import Deployment, MonitoringMode
from luml.schemas.monitoring import (
    MONITORING_READ_SCOPE,
    MonitoringEligibility,
    MonitoringIneligibilityReason,
    MonitoringLaunchToken,
    MonitoringTokenClaims,
    MonitoringTokenIntrospectOut,
)
from luml.schemas.permissions import Action, Resource
from luml.schemas.satellite import Satellite, SatelliteCapability

LAUNCH_TOKEN_EXPIRE_SECONDS = 300  # 5 minutes, short-lived launch credential


class MonitoringHandler:
    __deployment_repo = DeploymentRepository(engine)
    __satellite_repo = SatelliteRepository(engine)
    __launch_token_repo = MonitoringLaunchTokenRepository(engine)
    __permissions_handler = PermissionsHandler()

    def __init__(
        self,
        secret_key: str,
        algorithm: str = "HS256",
        launch_token_expire: int = LAUNCH_TOKEN_EXPIRE_SECONDS,
    ) -> None:
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.launch_token_expire = launch_token_expire

    @staticmethod
    def _eligibility(
        deployment: Deployment, satellite: Satellite
    ) -> MonitoringIneligibilityReason | None:
        if deployment.monitoring_mode != MonitoringMode.FULL:
            return MonitoringIneligibilityReason.MONITORING_OFF
        if SatelliteCapability.MONITORING not in satellite.capabilities:
            return MonitoringIneligibilityReason.CAPABILITY_MISSING
        return None

    async def _load_deployment_and_satellite(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        deployment_id: UUID,
    ) -> tuple[Deployment, Satellite]:
        await self.__permissions_handler.check_permissions(
            organization_id,
            user_id,
            Resource.DEPLOYMENT,
            Action.READ,
            orbit_id,
        )
        deployment = await self.__deployment_repo.get_deployment(
            deployment_id, orbit_id
        )
        if not deployment:
            raise NotFoundError("Deployment not found")
        satellite = await self.__satellite_repo.get_satellite(deployment.satellite_id)
        if not satellite:
            raise NotFoundError("Satellite not found")
        return deployment, satellite

    async def get_eligibility(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        deployment_id: UUID,
    ) -> MonitoringEligibility:
        deployment, satellite = await self._load_deployment_and_satellite(
            user_id, organization_id, orbit_id, deployment_id
        )
        reason = self._eligibility(deployment, satellite)
        return MonitoringEligibility(
            eligible=reason is None,
            satellite_base_url=satellite.base_url,
            reason=reason,
        )

    async def mint_launch_token(
        self,
        user_id: UUID,
        organization_id: UUID,
        orbit_id: UUID,
        deployment_id: UUID,
    ) -> MonitoringLaunchToken:
        deployment, satellite = await self._load_deployment_and_satellite(
            user_id, organization_id, orbit_id, deployment_id
        )
        if self._eligibility(deployment, satellite) is not None:
            raise ApplicationError(
                "Monitoring is not enabled for this deployment",
                status.HTTP_409_CONFLICT,
            )
        if not satellite.base_url:
            raise ApplicationError(
                "Satellite base URL is not configured",
                status.HTTP_409_CONFLICT,
            )

        expires_at = int(time.time()) + self.launch_token_expire
        claims = {
            "deployment_id": str(deployment_id),
            "satellite_id": str(deployment.satellite_id),
            "user_id": str(user_id),
            "scope": MONITORING_READ_SCOPE,
            "jti": str(uuid.uuid7()),
            "exp": expires_at,
        }
        token = jwt.encode(claims, self.secret_key, algorithm=self.algorithm)
        return MonitoringLaunchToken(
            token=token,
            satellite_base_url=satellite.base_url,
            expires_at=expires_at,
        )

    async def introspect_token(
        self, satellite_id: UUID, token: str
    ) -> MonitoringTokenIntrospectOut:
        try:
            payload: dict[str, Any] = jwt.decode(
                token, self.secret_key, algorithms=[self.algorithm]
            )
        except InvalidTokenError:
            return MonitoringTokenIntrospectOut(active=False)

        if payload.get("scope") != MONITORING_READ_SCOPE:
            return MonitoringTokenIntrospectOut(active=False)

        try:
            claims = MonitoringTokenClaims.model_validate(payload)
        except ValidationError:
            return MonitoringTokenIntrospectOut(active=False)

        if claims.satellite_id != satellite_id:
            return MonitoringTokenIntrospectOut(active=False)

        if not await self.__launch_token_repo.consume(claims.jti, claims.exp):
            return MonitoringTokenIntrospectOut(active=False)

        return MonitoringTokenIntrospectOut(active=True, claims=claims)
