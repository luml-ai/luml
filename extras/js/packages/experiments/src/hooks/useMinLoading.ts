import { ref, watch, type Ref } from 'vue'
import { useTimeoutFn } from '@vueuse/core'

export function useMinLoading(source: Ref<boolean>, minDuration = 500) {
  const display = ref(source.value)
  let startedAt = 0

  const { start, stop } = useTimeoutFn(
    () => {
      display.value = false
    },
    () => Math.max(0, minDuration - (Date.now() - startedAt)),
    { immediate: false },
  )

  watch(
    source,
    (loading) => {
      stop()
      if (loading) {
        startedAt = Date.now()
        display.value = true
      } else {
        start()
      }
    },
    { immediate: true },
  )

  return display
}
