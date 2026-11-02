import { ref } from 'vue'

export const usePageLoading = () => {
  const isLoading = ref(false)
  let generation = 0
  let loadId = 0

  function invalidate() {
    generation++
  }

  async function track(load: (isCurrent: () => boolean) => Promise<void>) {
    const id = ++loadId
    const loadGeneration = generation
    isLoading.value = true
    try {
      await load(() => loadGeneration === generation)
    } finally {
      if (id === loadId) isLoading.value = false
    }
  }

  return { isLoading, invalidate, track }
}
