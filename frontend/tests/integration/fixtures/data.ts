export const OrganizationRole = {
  owner: 'owner',
  admin: 'admin',
  member: 'member',
} as const
export type OrganizationRole = (typeof OrganizationRole)[keyof typeof OrganizationRole]

export const OrbitRole = {
  admin: 'admin',
  member: 'member',
} as const
export type OrbitRole = (typeof OrbitRole)[keyof typeof OrbitRole]

export const Permission = {
  list: 'list',
  read: 'read',
  create: 'create',
  update: 'update',
  delete: 'delete',
  deploy: 'deploy',
  leave: 'leave',
} as const

export const ORB_FULL_PERMISSIONS = {
  orbit: [
    Permission.list,
    Permission.read,
    Permission.create,
    Permission.update,
    Permission.delete,
  ],
  orbit_user: [
    Permission.list,
    Permission.read,
    Permission.create,
    Permission.update,
    Permission.delete,
  ],
  artifact: [
    Permission.list,
    Permission.read,
    Permission.create,
    Permission.update,
    Permission.delete,
  ],
  collection: [
    Permission.list,
    Permission.read,
    Permission.create,
    Permission.update,
    Permission.delete,
  ],
}

export const ORG_ID = '11111111-1111-1111-1111-111111111111'
export const ORG_ID_2 = '22222222-2222-2222-2222-222222222222'
export const USER_ID = '99999999-9999-9999-9999-999999999999'
export const USER_ID_2 = '88888888-8888-8888-8888-888888888888'
export const MEMBER_ID = '55555555-5555-5555-5555-555555555555'
export const MEMBER_ID_2 = '66666666-6666-6666-6666-666666666666'
export const INVITE_ID = '77777777-7777-7777-7777-777777777777'

export const USER_FIXTURE = {
  id: USER_ID,
  email: 'owner@example.com',
  full_name: 'Owner User',
  disabled: false,
  photo: '',
  has_api_key: false,
  auth_method: 'email' as const,
}

export const FULL_PERMISSIONS = {
  organization: [Permission.read, Permission.update, Permission.delete, Permission.leave],
  organization_user: [
    Permission.list,
    Permission.read,
    Permission.create,
    Permission.update,
    Permission.delete,
  ],
  organization_invite: [
    Permission.list,
    Permission.read,
    Permission.create,
    Permission.delete,
  ],
  billing: [Permission.read, Permission.update],
  orbit: [Permission.create],
}

export function makeOrganization(overrides: Record<string, unknown> = {}) {
  return {
    id: ORG_ID,
    name: 'Acme Corp',
    logo: null,
    role: OrganizationRole.owner,
    created_at: '2025-01-01T00:00:00.000Z',
    updated_at: '2025-01-01T00:00:00.000Z',
    members_count: 1,
    permissions: FULL_PERMISSIONS,
    ...overrides,
  }
}

export function makeMember(overrides: Record<string, unknown> = {}) {
  return {
    id: MEMBER_ID,
    organization_id: ORG_ID,
    role: OrganizationRole.owner,
    user: USER_FIXTURE,
    created_at: '2025-01-01T00:00:00.000Z',
    updated_at: null,
    ...overrides,
  }
}

export function makeInvitation(overrides: Record<string, unknown> = {}) {
  return {
    id: INVITE_ID,
    email: 'invitee@example.com',
    role: OrganizationRole.member,
    organization_id: ORG_ID,
    invited_by_user: {
      id: USER_ID,
      email: USER_FIXTURE.email,
      full_name: USER_FIXTURE.full_name,
      disabled: false,
      photo: '',
      has_api_key: false,
    },
    created_at: '2025-02-01T00:00:00.000Z',
  } as Record<string, unknown>
}

export function makeOrganizationDetails(overrides: Record<string, unknown> = {}) {
  return {
    ...makeOrganization(),
    invites: [],
    members: [makeMember()],
    orbits: [],
    members_limit: 10,
    orbits_limit: 5,
    satellites_limit: 3,
    artifacts_limit: 100,
    total_orbits: 0,
    total_members: 1,
    total_satellites: 0,
    total_artifacts: 0,
    members_by_role: {
      owner: 1,
      admin: 0,
      member: 0,
    },
    ...overrides,
  }
}


export const ORBIT_ID = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
export const ORBIT_ID_2 = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
export const BUCKET_ID = 'cccccccc-cccc-cccc-cccc-cccccccccccc'

export function makeOrbit(overrides: Record<string, unknown> = {}) {
  return {
    id: ORBIT_ID,
    name: 'Main Orbit',
    organization_id: ORG_ID,
    bucket_secret_id: BUCKET_ID,
    total_members: 1,
    total_collections: 0,
    total_satellites: 0,
    total_artifacts: 0,
    role: OrbitRole.admin,
    created_at: '2025-01-01T00:00:00.000Z',
    updated_at: null,
    permissions: ORB_FULL_PERMISSIONS,
    ...overrides,
  }
}

export function makeOrbitDetails(overrides: Record<string, unknown> = {}) {
  return {
    ...makeOrbit(),
    members: [],
    ...overrides,
  }
}

export function makeBucketSecret(overrides: Record<string, unknown> = {}) {
  return {
    id: BUCKET_ID,
    type: 's3',
    endpoint: 's3.amazonaws.com',
    bucket_name: 'main-bucket',
    secure: true,
    region: 'us-east-1',
    cert_check: true,
    organization_id: ORG_ID,
    created_at: '2025-01-01T00:00:00.000Z',
    updated_at: '2025-01-01T00:00:00.000Z',
    ...overrides,
  }
}

export function makeAzureBucketSecret(overrides: Record<string, unknown> = {}) {
  return {
    id: BUCKET_ID,
    type: 'azure',
    endpoint: 'DefaultEndpointsProtocol=https;AccountName=test;AccountKey=fake==',
    bucket_name: 'azure-container',
    organization_id: ORG_ID,
    created_at: '2025-01-01T00:00:00.000Z',
    updated_at: '2025-01-01T00:00:00.000Z',
    ...overrides,
  }
}

export const BUCKET_PRESIGNED_URL = 'https://fake-bucket.test/presigned-upload'
export const BUCKET_DOWNLOAD_URL = 'https://fake-bucket.test/download'
export const BUCKET_DELETE_URL = 'https://fake-bucket.test/delete'

export function makeBucketConnectionUrls() {
  return {
    presigned_url: BUCKET_PRESIGNED_URL,
    download_url: BUCKET_DOWNLOAD_URL,
    delete_url: BUCKET_DELETE_URL,
  }
}


export const CollectionType = {
  model: 'model',
  dataset: 'dataset',
  experiment: 'experiment',
  mixed: 'mixed',
} as const

export const COLLECTION_ID = 'dddddddd-dddd-dddd-dddd-dddddddddddd'
export const COLLECTION_ID_2 = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee'

export function makeCollection(overrides: Record<string, unknown> = {}) {
  return {
    id: COLLECTION_ID,
    orbit_id: ORBIT_ID,
    description: 'Main model collection',
    name: 'Main Collection',
    type: CollectionType.model,
    tags: ['production'],
    total_artifacts: 0,
    created_at: '2025-01-01T00:00:00.000Z',
    updated_at: '2025-01-01T00:00:00.000Z',
    ...overrides,
  }
}

export function makeCollectionsListResponse(
  items: ReturnType<typeof makeCollection>[] = [],
  cursor: string | null = null,
) {
  return { cursor, items }
}


export const ArtifactStatus = {
  uploaded: 'uploaded',
  upload_failed: 'upload_failed',
  deletion_failed: 'deletion_failed',
  pending_upload: 'pending_upload',
  pending_deletion: 'pending_deletion',
} as const

export const ArtifactType = {
  model: 'model',
  dataset: 'dataset',
  experiment: 'experiment',
} as const

export const ARTIFACT_ID = 'a1b2c3d4-a1b2-c3d4-e5f6-a1b2c3d4e5f6'
export const ARTIFACT_ID_2 = 'f6e5d4c3-f6e5-d4c3-b2a1-f6e5d4c3b2a1'

export function makeArtifact(overrides: Record<string, unknown> = {}) {
  return {
    id: ARTIFACT_ID,
    name: 'model-v1',
    description: 'First trained model',
    type: ArtifactType.model,
    status: ArtifactStatus.uploaded,
    tags: ['baseline'],
    file_name: 'model-v1.luml',
    file_hash: 'sha256:fake',
    file_index: {},
    size: 1024 * 1024 * 5,
    extra_values: {},
    manifest: {
      artifact_type: 'model',
      variant: 'tabular',
      name: 'model-v1',
      description: '',
      version: '1.0.0',
      producer_name: 'luml',
      producer_version: '1.0.0',
      producer_tags: ['tabular_classification'],
      payload: {},
    },
    created_at: '2025-02-01T00:00:00.000Z',
    updated_at: '2025-02-01T00:00:00.000Z',
    ...overrides,
  }
}

export function makeArtifactsListResponse(
  items: ReturnType<typeof makeArtifact>[] = [],
  cursor: string | null = null,
) {
  return { cursor, items }
}

export function makeExtendedCollection(overrides: Record<string, unknown> = {}) {
  return {
    ...makeCollection(),
    artifacts_extra_values: ['accuracy', 'f1_score', 'precision'],
    artifacts_tags: ['baseline', 'production'],
    ...overrides,
  }
}


export const DeploymentStatus = {
  pending: 'pending',
  active: 'active',
  failed: 'failed',
  deleted: 'deleted',
  deletion_pending: 'deletion_pending',
  not_responding: 'not_responding',
} as const

export const DEPLOYMENT_ID = 'fa11dafa-1111-2222-3333-444455556666'
export const DEPLOYMENT_ID_2 = 'fa11dafa-aaaa-bbbb-cccc-ddddeeeeffff'
export const SATELLITE_ID = '99999999-8888-7777-6666-555544443333'

export function makeDeployment(overrides: Record<string, unknown> = {}) {
  return {
    id: DEPLOYMENT_ID,
    orbit_id: ORBIT_ID,
    satellite_id: SATELLITE_ID,
    satellite_name: 'main-satellite',
    name: 'prod-deployment',
    artifact_id: ARTIFACT_ID,
    artifact_name: 'model-v1',
    collection_id: COLLECTION_ID,
    inference_url: 'https://infer.test/dep1',
    status: DeploymentStatus.active,
    satellite_parameters: {},
    description: 'Production deployment',
    dynamic_attributes_secrets: {},
    env_variables_secrets: {},
    env_variables: {},
    schemas: {},
    error_message: null,
    created_by_user: 'Owner User',
    tags: ['prod'],
    created_at: '2025-03-01T00:00:00.000Z',
    updated_at: '2025-03-01T00:00:00.000Z',
    ...overrides,
  }
}