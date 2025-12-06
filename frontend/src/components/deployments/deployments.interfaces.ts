import type {
  SatelliteFieldTypeEnum,
  SatelliteFieldValue,
  Validator,
} from '@/lib/api/satellites/interfaces'

export interface FieldInfo<T = string> {
  key: string
  value: T | null
  label: string
}

export interface SatelliteFieldInfo {
  key: string
  value: string | number | boolean | null
  label: string
  type: SatelliteFieldTypeEnum
  values: SatelliteFieldValue[] | null
  required: boolean
  validators: Validator[]
}

export interface CreateDeploymentForm {
  name: string
  description: string
  tags: string[]
  collectionId: string
  modelId: string
  satelliteId: string
  secretDynamicAttributes: FieldInfo<string>[]
  dynamicAttributes: FieldInfo<string>[]
  secretEnvs: FieldInfo<string>[]
  notSecretEnvs: FieldInfo<string>[]
  customVariables: Omit<FieldInfo<string>, 'label'>[]
  satelliteFields: SatelliteFieldInfo[]
}
