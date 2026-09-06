import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useFlowStore = defineStore('flow', () => {
  const isSidebarOpened = ref(true)

  function toggleSidebar() {
    isSidebarOpened.value = !isSidebarOpened.value
  }

  return {
    isSidebarOpened,
    toggleSidebar,
  }
})
