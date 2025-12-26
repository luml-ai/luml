import {
  ProviderModelsEnum,
  ProvidersEnum,
  ProviderStatus,
  type BaseProviderInfo,
  type ProviderModel,
  type ProviderWithModels,
} from './prompt-fusion.interfaces'
import OpenAi from '@/assets/img/providers/open-ai.svg'
import Ollama from '@/assets/img/providers/ollama.svg'
import { LocalStorageService } from '@/utils/services/LocalStorageService'
import GptModel from '@/assets/img/providers/gpt-model.svg'
import OllamaModel from '@/assets/img/providers/ollama-model.svg'

export const getProviders = (): BaseProviderInfo[] => {
  const settings = LocalStorageService.get('providersSettings')
  const savedOpenAiSettings = settings?.[ProvidersEnum.openAi]
  const savedOllamaSettings = settings?.[ProvidersEnum.ollama]
  const data = [
    {
      id: ProvidersEnum.openAi,
      image: OpenAi,
      name: 'OpenAI',
      status: ProviderStatus.disconnected,
      settings: [
        {
          id: 'apiKey',
          label: 'API Key',
          required: true,
          placeholder: 'Enter your API Key',
          value: savedOpenAiSettings?.apiKey || '',
        },
      ],
    },
    {
      id: ProvidersEnum.ollama,
      image: Ollama,
      name: 'Ollama',
      status: ProviderStatus.disconnected,
      disabled: false,
      settings: [
        {
          id: 'apiBase',
          label: 'API Base',
          required: true,
          placeholder: 'http://localhost:11434',
          value: savedOllamaSettings?.apiBase || '',
        },
      ],
    },
  ]
  return data.map((provider) => {
    return {
      ...provider,
      status: provider.disabled
        ? ProviderStatus.disconnected
        : provider.settings.reduce((acc: ProviderStatus, setting) => {
            if (setting.required && !setting.value) return ProviderStatus.disconnected
            return acc
          }, ProviderStatus.connected),
    }
  })
}

export const openAiModels: ProviderModel[] = [
  {
    id: ProviderModelsEnum.gpt4o,
    label: 'gpt-4o',
    icon: GptModel,
  },
  {
    id: ProviderModelsEnum.gpt4o_mini,
    label: 'gpt-4o-mini',
    icon: GptModel,
  },
  {
    id: ProviderModelsEnum.gpt4_1,
    label: 'gpt-4.1',
    icon: GptModel,
  },
  {
    id: ProviderModelsEnum.gpt4_1_mini,
    label: 'gpt-4.1-mini',
    icon: GptModel,
  },
  {
    id: ProviderModelsEnum.gpt4_1_nano,
    label: 'gpt-4.1-nano',
    icon: GptModel,
  },
]

export const ollamaModels: ProviderModel[] = [
  {
    id: ProviderModelsEnum.gemma3_4b,
    label: 'gemma-3:4b',
    icon: OllamaModel,
  },
  {
    id: ProviderModelsEnum.llama3_1_8b,
    label: 'llama-3.1:8b',
    icon: OllamaModel,
  },
  {
    id: ProviderModelsEnum.llama3_2_3b,
    label: 'llama-3.2:3b',
    icon: OllamaModel,
  },
  {
    id: ProviderModelsEnum.llama3_3_70b,
    label: 'llama-3.3:70b',
    icon: OllamaModel,
  },
  {
    id: ProviderModelsEnum.mistral_small3_1_24b,
    label: 'mistral-small-3.1:24b',
    icon: OllamaModel,
  },
  {
    id: ProviderModelsEnum.qwen2_5_7b,
    label: 'qwen-2.5:7b',
    icon: OllamaModel,
  },
  {
    id: ProviderModelsEnum.phi4_14b,
    label: 'phi-4:14b',
    icon: OllamaModel,
  },
  {
    id: ProviderModelsEnum.phi4_mini_3_8b,
    label: 'phi-4-mini-3:8b',
    icon: OllamaModel,
  },
]

export const getAllModels = (): ProviderWithModels[] => {
  const openAi = { label: 'OpenAI', providerId: ProvidersEnum.openAi, items: openAiModels }
  const ollama = { label: 'Ollama', providerId: ProvidersEnum.ollama, items: ollamaModels }
  return [openAi, ollama]
}

export const allModels = getAllModels()
