import type {
  FieldVariant,
  NodeTypeEnum,
  PromptFieldTypeEnum,
} from '@/components/express-tasks/prompt-fusion/interfaces'
import type { Node } from '@vue-flow/core'

export interface BaseProviderInfo {
  id: ProvidersEnum
  image: string
  name: string
  status: ProviderStatus
  settings: ProviderSetting[]
  disabled?: boolean
}

export enum ProvidersEnum {
  openAi = 'openAi',
  ollama = 'ollama',
}

export enum ProviderModelsEnum {
  gpt4o = 'gpt-4o',
  gpt4o_mini = 'gpt-4o-mini',
  gpt4_1 = 'gpt-4.1',
  gpt4_1_mini = 'gpt-4.1-mini',
  gpt4_1_nano = 'gpt-4.1-nano',
  gemma3_4b = 'gemma3:4b',
  llama3_1_8b = 'llama3.1:8b',
  llama3_2_3b = 'llama3.2:3b',
  llama3_3_70b = 'llama3.3:70b',
  mistral_small3_1_24b = 'mistral-small3.1:24b',
  qwen2_5_7b = 'qwen2.5:7b',
  phi4_14b = 'phi4:14b',
  phi4_mini_3_8b = 'phi4-mini:3.8b',
}

export enum ModelTypeEnum {
  teacher = 'teacher',
  student = 'student',
}

export enum ProviderStatus {
  connected = 'connected',
  disconnected = 'disconnected',
}

export enum EvaluationModesEnum {
  exactMatch = 'Exact match',
  llmBased = 'LLM-as-a-judge',
  none = 'None',
}

export interface ProviderSetting {
  id: string
  label: string
  required: boolean
  placeholder: string
  value: string
}

export interface ProviderModel {
  id: ProviderModelsEnum
  label: string
  icon: string
}

export interface ProviderWithModels {
  label: string
  providerId: ProvidersEnum
  items: ProviderModel[]
}

export interface PromptFusionPayload {
  data: PayloadData
  settings: PayloadSettings
  trainingData: Record<string, []>
}

export interface PayloadData {
  edges: PayloadEdge[]
  nodes: PayloadNode[]
}

export interface PayloadEdge {
  id: string
  sourceNode: string
  sourceField: string
  targetNode: string
  targetField: string
}

export interface PayloadNode extends Node {
  id: string
  data: PayloadNodeData
}

export interface PayloadNodeData {
  fields: PayloadNodeField[]
  type: NodeTypeEnum
  label: string
  hint?: string
}

export interface PayloadNodeField {
  id: string
  value: string
  variant: FieldVariant
  type: PromptFieldTypeEnum
  variadic: boolean
}

export interface PayloadSettings {
  taskDescription: string
  teacher: PayloadProviderData
  student: PayloadProviderData
  evaluationMode: EvaluationModesEnum
  criteriaList: string[]
}

export interface PayloadProviderData {
  providerId: ProvidersEnum
  modelId: ProviderModelsEnum
  providerSettings: Record<string, string>
}

export enum ProviderDynamicAttributesTagsEnum {
  'dataforce.studio/prompt-fusion::provider_api_key:v1' = 'apiKey',
  'dataforce.studio/prompt-fusion::provider_base_url:v1' = 'apiBase',
}

export enum ProviderAttributesMap {
  'apiKey' = 'api_key',
  'apiBase' = 'api_base',
}
