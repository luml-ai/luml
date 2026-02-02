export enum DeploymentStatusEnum {
  pending = 'pending',
  active = 'active',
  failed = 'failed',
  deleted = 'deleted',
  deletion_pending = 'deletion_pending',
  not_responding = 'not_responding',
}

export interface CreateDeploymentPayload {
  name: string
  description: string
  satellite_id: string
  artifact_id: string
  satellite_parameters: Record<string, string | number | boolean>
  dynamic_attributes_secrets: Record<string, string>
  env_variables_secrets: Record<string, string>
  env_variables: Record<string, string | number>
  tags: string[]
}

export interface Deployment {
  id: string
  orbit_id: string
  satellite_id: string
  artifact_id: string
  inference_url: string
  status: DeploymentStatusEnum
  secrets: Record<string, string>
  created_by_user: string
  tags: string[]
  created_at: string
  updated_at: string
  satellite_name: string
  name: string
  description: string
  collection_id: string
  dynamic_attributes_secrets: Record<string, string>
  artifact_name: string
  error_message: DeploymentErrorMessage | null
  schemas: object
}

export interface UpdateDeploymentPayload {
  name: string
  description: string
  tags: string[]
  dynamic_attributes_secrets: Record<string, string>
}

export interface DeploymentErrorMessage {
  error: string
  reason: string
}
