export interface FieldInfo<T = string> {
  key: string
  value: T | null
  label: string
}

export interface CreateDeploymentForm {
  name: string
  description: string
  tags: string[]
  collectionId: number
  modelId: number
  satelliteId: number
  secretDynamicAttributes: FieldInfo<number>[]
  dynamicAttributes: FieldInfo<string>[]
  secretEnvs: FieldInfo<number>[]
  notSecretEnvs: FieldInfo<string>[]
  customVariables: Omit<FieldInfo<string>, 'label'>[]
  satelliteFields: FieldInfo<string | number>[]
}
