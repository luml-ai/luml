from enum import StrEnum

from pydantic import BaseModel

from dataforce_studio.schemas.base import BaseOrmConfig
from dataforce_studio.schemas.orbit import OrbitRole
from dataforce_studio.schemas.organization import OrgRole


class Resource(StrEnum):
    ORGANIZATION = "organization"
    ORGANIZATION_USER = "organization_user"
    ORGANIZATION_INVITE = "organization_invite"
    ORBIT = "orbit"
    ORBIT_USER = "orbit_user"
    BILLING = "billing"
    BUCKET_SECRET = "bucket_secret"
    MODEL = "model"
    COLLECTION = "collection"
    SATELLITE = "satellite"
    ORBIT_SECRET = "orbit_secret"
    DEPLOYMENT = "deployment"


class Action(StrEnum):
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LIST = "list"
    LEAVE = "leave"
    DEPLOY = "deploy"
    ACCEPT = "accept"
    REJECT = "reject"


class OrgPermission(BaseModel, BaseOrmConfig):
    role: OrgRole | str
    resource: Resource
    action: Action


class OrbitPermission(BaseModel, BaseOrmConfig):
    role: OrbitRole | str
    resource: Resource
    action: Action


organization_permissions = {
    OrgRole.OWNER: {
        Resource.ORGANIZATION: [Action.READ, Action.UPDATE, Action.DELETE],
        Resource.ORGANIZATION_USER: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
        ],
        Resource.ORGANIZATION_INVITE: [
            Action.CREATE,
            Action.DELETE,
            Action.LIST,
            # Action.ACCEPT,
            # Action.REJECT,
            Action.READ,
        ],
        Resource.ORBIT: [
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
            Action.LIST,
            Action.READ,
        ],
        Resource.ORBIT_USER: [
            Action.LIST,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
            Action.READ,
        ],
        Resource.SATELLITE: [
            Action.CREATE,
            Action.LIST,
            Action.READ,
            Action.UPDATE,
            Action.DELETE,
        ],
        Resource.DEPLOYMENT: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
        ],
        Resource.ORBIT_SECRET: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
        ],
        Resource.BUCKET_SECRET: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
        ],
        Resource.MODEL: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
            Action.DEPLOY,
        ],
        Resource.COLLECTION: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
            Action.DEPLOY,
        ],
        Resource.BILLING: [Action.READ, Action.UPDATE],
    },
    OrgRole.ADMIN: {
        Resource.ORGANIZATION: [Action.READ, Action.UPDATE, Action.LEAVE],
        Resource.ORGANIZATION_USER: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
        ],
        Resource.ORGANIZATION_INVITE: [
            Action.CREATE,
            Action.DELETE,
            Action.LIST,
            # Action.ACCEPT,
            # Action.REJECT,
            Action.READ,
        ],
        Resource.ORBIT: [Action.CREATE, Action.UPDATE, Action.LIST, Action.READ],
        Resource.ORBIT_USER: [
            Action.LIST,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
            Action.READ,
        ],
        Resource.SATELLITE: [
            Action.CREATE,
            Action.LIST,
            Action.READ,
            Action.UPDATE,
            Action.DELETE,
        ],
        Resource.DEPLOYMENT: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
        ],
        Resource.ORBIT_SECRET: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
        ],
        Resource.BUCKET_SECRET: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
        ],
        Resource.COLLECTION: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
            Action.DEPLOY,
        ],
        Resource.MODEL: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
            Action.DEPLOY,
        ],
    },
    OrgRole.MEMBER: {
        Resource.ORGANIZATION: [Action.LEAVE],
        Resource.ORBIT: [Action.LIST, Action.READ],
        Resource.MODEL: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
            Action.DEPLOY,
        ],
        Resource.COLLECTION: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
            Action.DEPLOY,
        ],
    },
}

orbit_permissions = {
    OrbitRole.ADMIN: {
        Resource.ORBIT: [
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
            Action.LIST,
            Action.READ,
        ],
        Resource.ORBIT_USER: [
            Action.LIST,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
            Action.READ,
        ],
        Resource.MODEL: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
            Action.DEPLOY,
        ],
        Resource.COLLECTION: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
        ],
        Resource.SATELLITE: [
            Action.CREATE,
            Action.LIST,
            Action.READ,
            Action.UPDATE,
            Action.DELETE,
        ],
        Resource.DEPLOYMENT: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
        ],
        Resource.ORBIT_SECRET: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
            Action.DELETE,
        ],
    },
    OrbitRole.MEMBER: {
        Resource.ORBIT: [Action.LIST, Action.READ],
        Resource.MODEL: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
        ],
        Resource.COLLECTION: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
        ],
        Resource.DEPLOYMENT: [
            Action.LIST,
            Action.READ,
            Action.CREATE,
            Action.UPDATE,
        ],
        Resource.SATELLITE: [Action.CREATE, Action.LIST, Action.READ],
        Resource.ORBIT_SECRET: [Action.LIST, Action.CREATE],
    },
}
