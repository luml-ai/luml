import type { ProvidersEnum } from '@/lib/promt-fusion/prompt-fusion.interfaces'

export interface LocalStorageProviderSettings {
  saveApiKeys?: boolean
  [ProvidersEnum.openAi]?: Record<string, string>
  [ProvidersEnum.ollama]?: Record<string, string>
}
