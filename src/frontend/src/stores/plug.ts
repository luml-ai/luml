import { useWindowSize } from '@/hooks/useWindowSize'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'

export const usePlugStore = defineStore('plug', () => {
  const route = useRoute()
  const { width } = useWindowSize()

  const closed = ref(false)

  const visible = computed(() => {
    return !!(
      !closed.value &&
      route.meta.showInvalidMessage &&
      width.value < route.meta.showInvalidMessage
    )
  })

  function close() {
    closed.value = true
  }

  return { visible, close }
})
