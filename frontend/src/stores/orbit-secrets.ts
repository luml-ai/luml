import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/lib/api'
import type {
  OrbitSecret,
  CreateSecretPayload,
  UpdateSecretPayload,
} from '@/lib/api/orbit-secrets/interfaces'

export const useSecretsStore = defineStore('secrets', () => {
  const secretsList = ref<OrbitSecret[]>([])
  const creatorVisible = ref(false)

  const existingTags = computed((): string[] => {
    const tagsSet = secretsList.value.reduce((acc: Set<string>, item) => {
      item.tags?.forEach((tag: string) => acc.add(tag))
      return acc
    }, new Set<string>())
    return Array.from(tagsSet)
  })

  function showCreator() {
    creatorVisible.value = true
  }

  function hideCreator() {
    creatorVisible.value = false
  }

  async function loadSecrets(organizationId: string, orbitId: string) {
    secretsList.value = await api.orbitSecrets.getSecrets(organizationId, orbitId)
  }

  async function addSecret(organizationId: string, orbitId: string, payload: CreateSecretPayload) {
    await api.orbitSecrets.createSecret(organizationId, orbitId, payload)
    await loadSecrets(organizationId, orbitId)
  }

  async function updateSecret(
    organizationId: string,
    orbitId: string,
    payload: UpdateSecretPayload,
  ) {
    await api.orbitSecrets.updateSecret(organizationId, orbitId, payload)
    await loadSecrets(organizationId, orbitId)
  }

  async function deleteSecret(organizationId: string, orbitId: string, secretId: string) {
    await api.orbitSecrets.deleteSecret(organizationId, orbitId, secretId)
    secretsList.value = secretsList.value.filter((secret) => secret.id !== secretId)
  }

  async function getSecretById(organizationId: string, orbitId: string, secretId: string) {
    return await api.orbitSecrets.getSecretById(organizationId, orbitId, secretId)
  }

  function reset() {
    secretsList.value = []
    creatorVisible.value = false
  }

  return {
    secretsList,
    creatorVisible,
    existingTags,
    showCreator,
    hideCreator,
    loadSecrets,
    addSecret,
    updateSecret,
    deleteSecret,
    getSecretById,
    reset,
  }
})
