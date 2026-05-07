"""Idempotent dev-environment seed.

Creates an activated admin user, an organization, a sample orbit, and a
bucket secret pointing at the local MinIO instance — but only when each
piece is missing. Re-running this script is safe.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from uuid import UUID

from argon2 import PasswordHasher

from luml.repositories.bucket_secrets import BucketSecretRepository
from luml.repositories.orbits import OrbitRepository
from luml.repositories.users import UserRepository
from luml.schemas.bucket_secrets import S3BucketSecretCreate
from luml.schemas.orbit import OrbitCreateIn, OrbitMemberCreateSimple, OrbitRole
from luml.schemas.organization import OrganizationCreateIn
from luml.schemas.user import (
    AuthProvider,
    CreateUser,
    UpdateUser,
)

logging.basicConfig(level=logging.INFO, format="[seed] %(message)s")
log = logging.getLogger(__name__)


def _env(key: str, default: str | None = None) -> str:
    value = os.environ.get(key, default)
    if value is None:
        log.error("Missing required env var: %s", key)
        sys.exit(1)
    return value


async def _ensure_admin_user(repo: UserRepository) -> UUID:
    email = _env("DEV_ADMIN_EMAIL")
    password = _env("DEV_ADMIN_PASSWORD")
    full_name = _env("DEV_ADMIN_FULL_NAME", "Dev Admin")

    user = await repo.get_user(email)
    if user is None:
        log.info("Creating admin user %s", email)
        hashed = PasswordHasher().hash(password)
        user = await repo.create_user(
            CreateUser(
                email=email,
                full_name=full_name,
                hashed_password=hashed,
                auth_method=AuthProvider.EMAIL,
                email_verified=True,
            )
        )
    else:
        log.info("Admin user %s already exists", email)
        if not user.email_verified:
            log.info("Activating admin user %s", email)
            await repo.update_user(UpdateUser(email=email, email_verified=True))
    assert user.id is not None
    return user.id


async def _ensure_org(repo: UserRepository, user_id: UUID) -> UUID:
    org_name = _env("DEV_ORG_NAME")
    orgs = await repo.get_user_organizations(user_id)
    for org in orgs:
        if org.name == org_name:
            log.info("Organization %s already exists", org_name)
            return org.id

    if orgs:
        log.info("Using existing organization %s", orgs[0].name)
        return orgs[0].id

    log.info("Creating organization %s", org_name)
    created = await repo.create_organization(
        user_id, OrganizationCreateIn(name=org_name)
    )
    return created.id


async def _ensure_bucket_secret(repo: BucketSecretRepository, org_id: UUID) -> UUID:
    endpoint = _env("DEV_BUCKET_ENDPOINT")
    bucket_name = _env("DEV_BUCKET_NAME")

    existing = await repo.get_organization_bucket_secrets(org_id)
    for secret in existing:
        if secret.bucket_name == bucket_name and secret.endpoint == endpoint:
            log.info("Bucket secret for %s/%s already exists", endpoint, bucket_name)
            return secret.id

    log.info("Creating bucket secret for %s/%s", endpoint, bucket_name)
    created = await repo.create_bucket_secret(
        S3BucketSecretCreate(
            organization_id=org_id,
            endpoint=endpoint,
            bucket_name=bucket_name,
            access_key=_env("DEV_BUCKET_ACCESS_KEY"),
            secret_key=_env("DEV_BUCKET_SECRET_KEY"),
            region=_env("DEV_BUCKET_REGION", "us-east-1"),
            secure=False,
            cert_check=False,
        )
    )
    return created.id


async def _ensure_orbit(
    repo: OrbitRepository,
    org_id: UUID,
    user_id: UUID,
    bucket_secret_id: UUID,
) -> UUID:
    orbit_name = _env("DEV_ORBIT_NAME")

    existing = await repo.get_organization_orbits(org_id)
    for orbit in existing:
        if orbit.name == orbit_name:
            log.info("Orbit %s already exists", orbit_name)
            return orbit.id

    log.info("Creating orbit %s", orbit_name)
    created = await repo.create_orbit(
        org_id,
        OrbitCreateIn(
            name=orbit_name,
            bucket_secret_id=bucket_secret_id,
            members=[
                OrbitMemberCreateSimple(user_id=user_id, role=OrbitRole.ADMIN)
            ],
        ),
    )
    if created is None:
        raise RuntimeError("Failed to create orbit")
    return created.id


async def main() -> None:
    from luml.infra.db import engine

    user_repo = UserRepository(engine)
    bucket_repo = BucketSecretRepository(engine)
    orbit_repo = OrbitRepository(engine)

    user_id = await _ensure_admin_user(user_repo)
    org_id = await _ensure_org(user_repo, user_id)
    bucket_id = await _ensure_bucket_secret(bucket_repo, org_id)
    await _ensure_orbit(orbit_repo, org_id, user_id, bucket_id)

    log.info("Seed complete.")
    log.info("  Login:    %s", os.environ["DEV_ADMIN_EMAIL"])
    log.info("  Password: %s", os.environ["DEV_ADMIN_PASSWORD"])


if __name__ == "__main__":
    asyncio.run(main())
