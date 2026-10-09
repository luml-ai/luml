import { api } from '@/lib/api'
import type {
  IPostSignInRequest,
  IPostSignInResponse,
  IPostSignupRequest,
} from '@/lib/api/api.interfaces'
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
  const isLoggingOut = ref(false)
  let authCheck: Promise<void> | undefined

  const signUp = async (data: IPostSignupRequest) => {
    await api.signUp(data)
  }

  const signIn = async (data: IPostSignInRequest) => {
    const response: IPostSignInResponse = await api.signIn(data)
    authCheck = Promise.resolve()
    isAuth.value = true
    await usersStore.loadUser()
    AnalyticsService.identify(response.user_id, data.email)
  }

  const loginWithGoogle = async (code: string) => {
    const response = await api.googleLogin({ code })
    authCheck = Promise.resolve()
    isAuth.value = true
    await usersStore.loadUser()

    if (usersStore.getUserEmail) {
      AnalyticsService.identify(response.user_id, usersStore.getUserEmail)
    }
  }

  const logout = async () => {
    if (isLoggingOut.value) {
      return
    }
    isLoggingOut.value = true
    try {
      await api.logout()
    } catch (e) {
      console.error('Logout error:', e)
    } finally {
      authCheck = Promise.resolve()
      usersStore.resetUser()
      isAuth.value = false
      isLoggingOut.value = false
      if (route.meta.requireAuth) {
        setTimeout(() => {
          router.push({ name: 'home' }).catch(() => {})
        }, 0)
      }
    }
  }

  const checkIsLoggedIn = () => {
    if (!authCheck) {
      const check = usersStore.loadUser().then(
        () => {
          if (authCheck === check) isAuth.value = true
        },
        () => {
          if (authCheck === check) isAuth.value = false
        },
      )
      authCheck = check
    }
    return authCheck
  }

  const forgotPassword = async (email: string) => {
    await api.forgotPassword({ email })
  }

  if (typeof window !== 'undefined') {
    const handleAuthLogout = () => {
      logout()
    }
    window.addEventListener('auth:logout', handleAuthLogout)
  }

  const loginWithMicrosoft = async (code: string) => {
    const response = await api.microsoftLogin({ code })
    authCheck = Promise.resolve()
    isAuth.value = true
    await usersStore.loadUser()
    if (usersStore.getUserEmail) {
      AnalyticsService.identify(response.user_id, usersStore.getUserEmail)
    }
  }

  return {
    isAuth,
    signUp,
    signIn,
    logout,
    checkIsLoggedIn,
    forgotPassword,
    loginWithGoogle,
    loginWithMicrosoft,
  }
})
