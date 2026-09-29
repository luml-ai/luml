export enum SatelliteTaskTypeEnum {
  pairing = 'pairing',
  deploy = 'deploy',
  undeploy = 'undeploy',
}

export enum SatelliteTaskStatusEnum {
  pending = 'pending',
  running = 'running',
  done = 'done',
  failed = 'failed',
}

export enum SatelliteStatusEnum {
  active = 'active',
  inactive = 'inactive',
  error = 'error',
}

export interface CreateSatellitePayload {
  name: string
  description: string
}

export interface CreateSatelliteResponse {
  satellite: Satellite
  api_key: string
  task: SatelliteTask
}

export interface Satellite {
  id: string
  orbit_id: string
  name: string
  description: string
  base_url: string | null
  paired: boolean
  capabilities: SatelliteCapabilities
  present_capabilities: string[]
  created_at: string
  updated_at: string
  last_seen_at: string
  status: SatelliteStatusEnum
  slug?: string
  kit_info?: SatelliteKitInfo | null
}

export interface SatelliteKitInfo {
  name: string
  version: string
  kind: string
  api_version: number
}

export interface CapabilityEnvelope {
  version: number
  api_versions?: number[]
  facets?: string[]
  [field: string]: unknown
}

export interface SatelliteCapabilities {
  [name: string]: CapabilityEnvelope | undefined
  deploy?: CapabilitiesDeploy
  monitoring?: CapabilitiesMonitoring
}

export enum MonitoringFeature {
  runtime = 'runtime',
  traces = 'traces',
  alerts = 'alerts',
  data_quality = 'data_quality',
  feature_drift = 'feature_drift',
  output_drift = 'output_drift',
  multivariate_drift = 'multivariate_drift',
}

export interface CapabilitiesMonitoring extends CapabilityEnvelope {
  version: 1
  api_versions: number[]
  facets: string[]
  features: MonitoringFeature[]
}

export interface CapabilitiesDeploy extends CapabilityEnvelope {
  version: 1
  api_versions: number[]
  facets: string[]
  supported_variants: string[]
  supported_tags_combinations: string[][] | null
  extra_fields_form_spec: SatelliteField[]
}

export interface SatelliteTask {
  id: string
  satellite_id: string
  orbit_id: string
  type: SatelliteTaskTypeEnum
  payload: object
  status: SatelliteTaskStatusEnum
  scheduled_at: string
  started_at: string
  finished_at: string
  result: object
  created_at: string
  updated_at: string
}

export interface RegenerateApiKeyResponse {
  key: string
}

export enum SatelliteFieldTypeEnum {
  boolean = 'boolean',
  dropdown = 'dropdown',
  text = 'text',
  number = 'number',
}

export type FieldOperator =
  | 'includes'
  | 'notIncludes'
  | 'equal'
  | 'notEqual'
  | 'gt'
  | 'gte'
  | 'lt'
  | 'lte'

type ValidatorType = 'min' | 'max' | 'regex' | 'equal' | 'in' | 'notEqual'

type ConditionType = 'field' | 'model'

export type ModelTagsOperator = 'includes' | 'notIncludes'

export type ModelVersionOperator = 'eq' | 'neq'

export type ModelVariantOperator = 'includes' | 'notIncludes' | 'eq' | 'neq'

export type ModelConditionObject =
  | ModelTagsConditionObject
  | ModelVersionConditionObject
  | ModelVariantConditionObject

export type SatelliteFieldValue = {
  label: string
  value: string | number
}

export interface SatelliteField {
  name: string
  type: SatelliteFieldTypeEnum
  values: SatelliteFieldValue[] | null
  required: boolean
  validators: Validator[]
  conditions: ConditionsObject[]
  default?: string | number | boolean | null
}

export interface Validator {
  type: ValidatorType
  value: unknown
  message?: string
}

export interface ConditionsObject {
  type: ConditionType
  body: FieldConditionObject | ModelConditionObject | ConditionsObject[]
}

export interface FieldConditionObject {
  field: string
  operator: FieldOperator
  value: unknown
}

interface ModelTagsConditionObject {
  field: 'tags'
  operator: ModelTagsOperator
  value: unknown
}

interface ModelVersionConditionObject {
  field: 'version'
  operator: ModelVersionOperator
  value: unknown
}

interface ModelVariantConditionObject {
  field: 'variant'
  operator: ModelVariantOperator
  value: unknown
}
