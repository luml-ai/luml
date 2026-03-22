import { ref } from 'vue'
import { defineStore } from 'pinia'
import { apiService } from '@/api/api.service'

export const useAuthStore = defineStore('auth', () => {
  const isAuthenticated = ref<boolean>(false)
  const apiKeyModalVisible = ref<boolean>(false)

  async function checkAuth() {
    const { has_key } = await apiService.checkAuth()
    isAuthenticated.value = has_key
    return isAuthenticated.value
  }

  async function setApiKey(apiKey: string) {
    await apiService.setApiKey(apiKey)
    isAuthenticated.value = true
  }

  function showApiKeyModal() {
    apiKeyModalVisible.value = true
  }

  function hideApiKeyModal() {
    apiKeyModalVisible.value = false
  }

  return {
    isAuthenticated,
    checkAuth,
    setApiKey,
    showApiKeyModal,
    apiKeyModalVisible,
    hideApiKeyModal,
  }
})
