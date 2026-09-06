import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useFlowStore = defineStore('flow', () => {
  const isSidebarOpened = ref(true)
  const viewMode = ref<'canvas' | 'notebook'>('canvas')

  function toggleSidebar() {
    isSidebarOpened.value = !isSidebarOpened.value
  }

  function setViewMode(mode: 'canvas' | 'notebook') {
    viewMode.value = mode
  }

  return {
    isSidebarOpened,
    toggleSidebar,
    viewMode,
    setViewMode,
  }
})
