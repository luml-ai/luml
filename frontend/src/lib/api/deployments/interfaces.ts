export enum DeploymentStatusEnum {
  pending = 'pending',
  active = 'active',
  failed = 'failed',
  deleted = 'deleted',
  deletion_pending = 'deletion_pending',
}

export interface CreateDeploymentPayload {
  name: string
  description: string
  satellite_id: number
  model_artifact_id: number
  satellite_parameters: Record<string, string | number>
  dynamic_attributes_secrets: Record<string, number>
  env_variables_secrets: Record<string, number>
  env_variables: Record<string, string | number>
  tags: string[]
}

export interface Deployment {
  id: number
  orbit_id: number
  satellite_id: number
  model_id: number
  inference_url: string
  status: DeploymentStatusEnum
  secrets: Record<string, number>
  created_by_user: string
  tags: string[]
  created_at: string
  updated_at: string
  satellite_name: string
  name: string
  description: string
  collection_id: number
  dynamic_attributes_secrets: Record<string, number>
  model_artifact_name: string
}

export interface UpdateDeploymentPayload {
  name: string
  description: string
  tags: string[]
  dynamic_attributes_secrets: Record<string, number>
}
