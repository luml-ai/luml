import { dataforceApi } from '@/lib/api'
import type {
  IPostSignInRequest,
  IPostSignInResponse,
  IPostSignupRequest,
} from '@/lib/api/DataforceApi.interfaces'
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { useUserStore } from './user'
import { AnalyticsService } from '@/lib/analytics/AnalyticsService'
import { useRoute, useRouter } from 'vue-router'

export const useAuthStore = defineStore('auth', () => {
  const usersStore = useUserStore()
  const route = useRoute()
  const router = useRouter()

  const isAuth = ref(false)

  const signUp = async (data: IPostSignupRequest) => {
    await dataforceApi.signUp(data)
  }

  const signIn = async (data: IPostSignInRequest) => {
    const { token, user_id }: IPostSignInResponse = await dataforceApi.signIn(data)
    saveTokens(token.access_token, token.refresh_token)
    isAuth.value = true
    AnalyticsService.identify(user_id, data.email)
    await usersStore.loadUser()
  }

  const logout = async () => {
    const refresh_token = localStorage.getItem('refreshToken')
    if (!refresh_token) throw new Error('Refresh token is not exist')
    try {
      await dataforceApi.logout({ refresh_token })
    } catch (e) {
      throw e
    } finally {
      localStorage.removeItem('token')
      localStorage.removeItem('refreshToken')
      usersStore.resetUser()
      isAuth.value = false
      if (route.meta.requireAuth) router.push({ name: 'home' })
    }
  }

  const checkIsLoggedId = async () => {
    if (isAuth.value) return
    const token = localStorage.getItem('token')
    const refreshToken = localStorage.getItem('refreshToken')
    if (!token && !refreshToken) {
      isAuth.value = false
      return
    }
    await usersStore.loadUser()
    isAuth.value = true
  }

  const saveTokens = (token: string, refreshToken?: string) => {
    localStorage.setItem('token', token)
    refreshToken && localStorage.setItem('refreshToken', refreshToken)
  }

  const forgotPassword = async (email: string) => {
    await dataforceApi.forgotPassword({ email })
  }

  const loginWithGoogle = async (code: string) => {
    const { token, user_id } = await dataforceApi.googleLogin({ code })
    if (!token.access_token) return
    saveTokens(token.access_token, token.refresh_token)
    isAuth.value = true
    await usersStore.loadUser()
    if (usersStore.getUserEmail) AnalyticsService.identify(user_id, usersStore.getUserEmail)
  }

  const loginWithMicrosoft = async (code: string) => {
    const { token, user_id } = await dataforceApi.microsoftLogin({ code })
    if (!token.access_token) return
    saveTokens(token.access_token, token.refresh_token)
    isAuth.value = true
    await usersStore.loadUser()
    if (usersStore.getUserEmail) AnalyticsService.identify(user_id, usersStore.getUserEmail)
  }

  return {
    isAuth,
    signUp,
    signIn,
    logout,
    checkIsLoggedId,
    forgotPassword,
    loginWithGoogle,
    loginWithMicrosoft,
  }
})
