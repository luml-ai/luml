import { ref } from 'vue'
import {
  TarAttachmentsProvider,
  type TarAttachmentsProviderConfig,
} from '@/modules/model-attachments/models/TarAttachmentsProvider'
import type { ModelAttachmentsProvider } from '@/modules/model-attachments'

export function useTarAttachmentsProvider() {
  const provider = ref<ModelAttachmentsProvider | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function init(config: TarAttachmentsProviderConfig): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const tarProvider = new TarAttachmentsProvider(config)
      await tarProvider.init()
      provider.value = tarProvider
    } catch (e) {
      console.error('Failed to initialize attachments provider:', e)
      error.value = e instanceof Error ? e.message : 'Unknown error'
      throw e
    } finally {
      loading.value = false
    }
  }

  return {
    provider,
    loading,
    error,
    init,
  }
}
