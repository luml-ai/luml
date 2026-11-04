import { defineStore } from 'pinia'
import type { IUser } from './user.interfaces'
import { computed, ref, watch } from 'vue'
import { api } from '@/lib/api'
import type { IPostChangePasswordRequest, IUpdateUserRequest } from '@/lib/api/api.interfaces'
import { useAuthStore } from './auth'
import { useOrganizationStore } from './organization'
import { useInvitationsStore } from './invitations'
import { useCollectionsStore } from './collections'
import { useTracksStore } from './tracks'
import { useDeploymentsStore } from './deployments'
import { useSecretsStore } from './orbit-secrets'

export const useUserStore = defineStore('user', () => {
  const authStore = useAuthStore()
  const invitationsStore = useInvitationsStore()
  const organizationStore = useOrganizationStore()

  const user = ref<IUser | null>(null)
  const isPasswordHasBeenChanged = ref(false)
  let userRequestId = 0

  const getUserEmail = computed(() => user.value?.email)
  const getUserFullName = computed(() => user.value?.full_name)
  const isUserDisabled = computed(() => user.value?.disabled)
  const getUserAvatar = computed(() => user.value?.photo)
  const isUserLoggedWithSSO = computed(() => user.value?.auth_method !== 'EMAIL')
  const getUserId = computed(() => user.value?.id)
  const isUserApiKeyExist = computed(() => !!user.value?.has_api_key)

  const loadUser = async () => {
    const requestId = ++userRequestId
    const data = await api.getMe()
    if (requestId === userRequestId) user.value = data
  }

  const changePassword = async (data: IPostChangePasswordRequest) => {
    await api.changePassword(data)
  }

  const deleteAccount = async () => {
    await api.deleteUser()

    authStore.logout()
  }

  const resetUser = () => {
    userRequestId++
    user.value = null
    isPasswordHasBeenChanged.value = false
    invitationsStore.reset()
    organizationStore.reset()
    useCollectionsStore().reset()
    useTracksStore().reset()
    useDeploymentsStore().reset()
    useSecretsStore().reset()
  }

  const resetPassword = async (reset_token: string, new_password: string) => {
    return api.resetPassword({ reset_token, new_password })
  }

  const updateUser = async (data: IUpdateUserRequest) => {
    const response = await api.updateUser(data)

    await loadUser()

    return response
  }

  const createApiKey = async () => {
    if (!user.value) return null
    const { key } = await api.apiKeys.createApiKey()
    user.value.has_api_key = true
    return key
  }

  const deleteApiKey = async () => {
    if (!user.value) return
    await api.apiKeys.deleteApiKey()
    user.value.has_api_key = false
  }

  watch(
    () => user.value?.id,
    async (id, _previousId, onCleanup) => {
      let stale = false
      onCleanup(() => {
        stale = true
      })
      if (id) {
        await invitationsStore.getInvitations().catch(() => undefined)
        if (!stale && user.value?.id === id) {
          await organizationStore.getAvailableOrganizations()
        }
      }
    },
  )

  return {
    getUserEmail,
    getUserFullName,
    getUserAvatar,
    isUserDisabled,
    isPasswordHasBeenChanged,
    isUserLoggedWithSSO,
    getUserId,
    isUserApiKeyExist,
    loadUser,
    changePassword,
    deleteAccount,
    resetUser,
    resetPassword,
    updateUser,
    createApiKey,
    deleteApiKey,
  }
})
