import { api } from '@/api/client'
import type { Model } from '@/store/experiments/experiments.interface'
import type { ModelCardZip } from './model.interface'

export const modelApi = {
  getModel: async (modelId: string) => {
    const { data } = await api.get<Model>(`/models/${modelId}`)
    return data
  },

  getModelCard: async (modelId: string) => {
    const { data } = await api.get<ModelCardZip>(`/models/${modelId}/card`, {
      responseType: 'arraybuffer',
    })
    return data
  },
}
