import { onBeforeUnmount, onMounted, ref } from 'vue'

export const useAppScrollbarFix = () => {
  const resizeObserver = new ResizeObserver(() => {
    calcScrollbarWidth()
  })

  const bodyElement = ref<HTMLBodyElement | null>(null)

  function calcScrollbarWidth() {
    const root = document.documentElement
    const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth
    root.style.setProperty('--p-scrollbar-width', scrollbarWidth + 'px')
  }

  onMounted(() => {
    bodyElement.value = document.querySelector('body')

    if (bodyElement.value) {
      resizeObserver.observe(bodyElement.value)
    }

    window.addEventListener('resize', calcScrollbarWidth)
  })

  onBeforeUnmount(() => {
    if (bodyElement.value) {
      resizeObserver.unobserve(bodyElement.value)
    }
    window.removeEventListener('resize', calcScrollbarWidth)
  })
}
