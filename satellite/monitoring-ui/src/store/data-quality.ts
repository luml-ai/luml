import { ref } from 'vue'
import { defineStore } from 'pinia'

export const useDataQualityStore = defineStore('data-quality', () => {
  const inspectedFeature = ref<string | null>(null)

  function inspect(feature: string | null) {
    inspectedFeature.value = feature
  }

  return { inspectedFeature, inspect }
})
