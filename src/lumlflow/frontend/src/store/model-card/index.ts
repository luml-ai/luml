import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useToast } from 'primevue'
import { errorToast } from '@/toasts'
import { apiService } from '@/api/api.service'
import type { Model } from '../experiments/experiments.interface'
import {
  createHtmlBlobUrl,
  extractHtmlFromModelCardZip,
} from '@/components/model-card/model-card.utils'

export const useModelCardStore = defineStore('model-card', () => {
  const toast = useToast()

  const dialogVisible = ref(false)
  const modelData = ref<Model | null>(null)
  const modelCardHtmlUrl = ref<string | null>(null)
  const modelCardLoading = ref(false)

  function revokeModelCardUrl() {
    if (modelCardHtmlUrl.value) {
      URL.revokeObjectURL(modelCardHtmlUrl.value)
      modelCardHtmlUrl.value = null
    }
  }

  async function showModelCard(modelId: string) {
    dialogVisible.value = true
    revokeModelCardUrl()
    modelCardLoading.value = true

    try {
      await new Promise((resolve) => setTimeout(resolve, 2000))
      modelData.value = await apiService.getModel(modelId)
      await loadModelCard(modelId)
    } catch {
      toast.add(errorToast('Failed to load model card'))
      hideModelCard()
    }
  }

  function hideModelCard() {
    dialogVisible.value = false
    modelCardLoading.value = false
    modelData.value = null
    revokeModelCardUrl()
  }

  async function loadModelCard(modelId: string) {
    try {
      const zipData = await apiService.getModelCard(modelId)
      const html = await extractHtmlFromModelCardZip(zipData)
      revokeModelCardUrl()
      modelCardHtmlUrl.value = createHtmlBlobUrl(html)
    } catch {
      revokeModelCardUrl()
    } finally {
      modelCardLoading.value = false
    }
  }

  return {
    dialogVisible,
    modelData,
    modelCardHtmlUrl,
    modelCardLoading,
    showModelCard,
    hideModelCard,
  }
})
