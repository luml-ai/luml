import { ref, watch, onUnmounted, type Ref } from 'vue'

export function useDeferredLoading(loading: Ref<boolean>, delayMs = 150) {
  const showSkeleton = ref(false)
  let timer: ReturnType<typeof setTimeout> | null = null

  watch(
    loading,
    (isLoading) => {
      if (isLoading) {
        timer = setTimeout(() => {
          if (loading.value) {
            showSkeleton.value = true
          }
        }, delayMs)
      } else {
        if (timer) {
          clearTimeout(timer)
          timer = null
        }
        showSkeleton.value = false
      }
    },
    { immediate: true },
  )

  onUnmounted(() => {
    if (timer) clearTimeout(timer)
  })

  return { showSkeleton }
}
