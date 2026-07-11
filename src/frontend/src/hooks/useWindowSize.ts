import { onMounted, onUnmounted, ref } from 'vue'

export const useWindowSize = () => {
  const width = ref(0)
  const height = ref(0)

  function onResize() {
    width.value = window.innerWidth
    height.value = window.innerHeight
  }

  onMounted(() => {
    onResize()
    window.addEventListener('resize', onResize)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', onResize)
  })

  return {
    width,
    height,
  }
}
