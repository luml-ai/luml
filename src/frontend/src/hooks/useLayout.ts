import { onMounted, onUnmounted, ref } from 'vue'

export const useLayout = () => {
  const header = ref<HTMLElement | null>()
  const sidebar = ref<HTMLElement | null>()
  const footer = ref<HTMLElement | null>()

  const resizeObserver = new ResizeObserver((entries) => {
    entries.map((entry) => {
      if (entry.target.id === 'header') {
        setHeaderSizes()
      } else if (entry.target.id === 'sidebar') {
        setSidebarSizes()
      } else if (entry.target.id === 'footer') {
        setFooterSizes()
      }
    })
  })

  const headerSizes = ref({
    width: 0,
    height: 0,
  })
  const sidebarSizes = ref({
    width: 0,
    height: 0,
  })
  const footerSizes = ref({
    width: 0,
    height: 0,
  })

  function setHeaderSizes() {
    if (header.value) {
      headerSizes.value.width = header.value.clientWidth
      headerSizes.value.height = header.value.clientHeight
    }
  }

  function setSidebarSizes() {
    if (sidebar.value) {
      sidebarSizes.value.width = sidebar.value.clientWidth
      sidebarSizes.value.height = sidebar.value.clientHeight
    }
  }

  function setFooterSizes() {
    if (footer.value) {
      footerSizes.value.width = footer.value.clientWidth
      footerSizes.value.height = footer.value.clientHeight
    }
  }

  onMounted(() => {
    header.value = document.getElementById('header')
    if (header.value) {
      resizeObserver.observe(header.value)
    }

    sidebar.value = document.getElementById('sidebar')
    if (sidebar.value) {
      resizeObserver.observe(sidebar.value)
    }

    footer.value = document.getElementById('footer')
    if (footer.value) {
      resizeObserver.observe(footer.value)
    }
  })

  onUnmounted(() => {
    if (header.value) {
      resizeObserver.unobserve(header.value)
    }
    if (sidebar.value) {
      resizeObserver.unobserve(sidebar.value)
    }
    if (footer.value) {
      resizeObserver.unobserve(footer.value)
    }
  })

  return { headerSizes, sidebarSizes, footerSizes }
}
