import { createPinia, setActivePinia } from 'pinia'
import type { NavigationGuardNext, RouteLocationNormalized } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiMocks = vi.hoisted(() => ({
  signIn: vi.fn(),
  googleLogin: vi.fn(),
  microsoftLogin: vi.fn(),
  logout: vi.fn(),
}))
const userStore = vi.hoisted(() => ({
  loadUser: vi.fn(),
  resetUser: vi.fn(),
  getUserEmail: 'user@example.com',
}))

vi.mock('@/lib/api', () => ({ api: apiMocks }))
vi.mock('@/stores/user', () => ({ useUserStore: () => userStore }))
vi.mock('@/lib/analytics/AnalyticsService', () => ({
  AnalyticsService: { identify: vi.fn() },
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ meta: {} }),
  useRouter: () => ({ push: vi.fn() }),
}))

import { useAuthStore } from '../auth'
import { authMiddleware } from '@/router/middlewares/AuthMiddleware'

const from = {} as RouteLocationNormalized

const navigate = async (fullPath: string, meta = {}) => {
  const next = vi.fn() as NavigationGuardNext
  await authMiddleware({ fullPath, meta } as RouteLocationNormalized, from, next)
  return next
}

describe('authentication session check', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
    userStore.loadUser.mockRejectedValue(new Error('Unauthorized'))
  })

  it('checks anonymous users once while navigating public pages', async () => {
    for (const path of ['/', '/sign-in', '/sign-up', '/setup']) {
      const next = await navigate(path)
      expect(next).toHaveBeenCalledOnce()
      expect(next).toHaveBeenCalledWith()
    }

    expect(useAuthStore().isAuth).toBe(false)
    expect(userStore.loadUser).toHaveBeenCalledOnce()
  })

  it('restores an existing session on a public entry page', async () => {
    userStore.loadUser.mockResolvedValue(undefined)

    const next = await navigate('/setup')

    expect(next).toHaveBeenCalledWith()
    expect(useAuthStore().isAuth).toBe(true)
    expect(userStore.loadUser).toHaveBeenCalledOnce()
  })

  it('shares the initial session check between concurrent navigations', async () => {
    let rejectCheck = (_error: Error) => {}
    userStore.loadUser.mockReturnValue(
      new Promise<void>((_resolve, reject) => {
        rejectCheck = reject
      }),
    )

    const publicNavigation = navigate('/')
    const protectedNavigation = navigate('/invitations', {
      requireAuth: true,
      redirectToSignIn: true,
    })
    expect(userStore.loadUser).toHaveBeenCalledOnce()

    rejectCheck(new Error('Unauthorized'))
    const [publicNext, protectedNext] = await Promise.all([publicNavigation, protectedNavigation])
    expect(publicNext).toHaveBeenCalledWith()
    expect(protectedNext).toHaveBeenCalledWith({
      name: 'sign-in',
      query: { redirect: '/invitations' },
    })
  })

  it('keeps protected routes guarded after an anonymous session check', async () => {
    await navigate('/')

    const next = await navigate('/dashboard', { requireAuth: true })
    const invitationNext = await navigate('/invitations', {
      requireAuth: true,
      redirectToSignIn: true,
    })

    expect(next).toHaveBeenCalledWith({ name: 'home' })
    expect(invitationNext).toHaveBeenCalledWith({
      name: 'sign-in',
      query: { redirect: '/invitations' },
    })
    expect(userStore.loadUser).toHaveBeenCalledOnce()
  })

  it('does not repeat a failed session check on navigation', async () => {
    userStore.loadUser.mockRejectedValue(new Error('Network unavailable'))

    await navigate('/')
    const next = await navigate('/sign-in')

    expect(next).toHaveBeenCalledWith()
    expect(useAuthStore().isAuth).toBe(false)
    expect(userStore.loadUser).toHaveBeenCalledOnce()
  })

  it.each(['email', 'Google', 'Microsoft'])(
    'allows %s login after an anonymous check',
    async (method) => {
      await navigate('/')
      userStore.loadUser.mockResolvedValue(undefined)
      const store = useAuthStore()

      if (method === 'email') {
        apiMocks.signIn.mockResolvedValue({ user_id: 1 })
        await store.signIn({ email: 'user@example.com', password: 'password' })
      } else if (method === 'Google') {
        apiMocks.googleLogin.mockResolvedValue({ user_id: 1 })
        await store.loginWithGoogle('code')
      } else {
        apiMocks.microsoftLogin.mockResolvedValue({ user_id: 1 })
        await store.loginWithMicrosoft('code')
      }
      const next = await navigate('/dashboard', { requireAuth: true })

      expect(store.isAuth).toBe(true)
      expect(next).toHaveBeenCalledWith()
      expect(userStore.loadUser).toHaveBeenCalledTimes(2)

      await store.logout()
      await navigate('/sign-in')
      expect(store.isAuth).toBe(false)
      expect(userStore.resetUser).toHaveBeenCalledOnce()
      expect(userStore.loadUser).toHaveBeenCalledTimes(2)
    },
  )

  it('does not check a session after an explicit logout before initial navigation', async () => {
    await useAuthStore().logout()

    await navigate('/')

    expect(useAuthStore().isAuth).toBe(false)
    expect(userStore.loadUser).not.toHaveBeenCalled()
  })

  it('preserves login when an earlier session check fails afterward', async () => {
    let rejectCheck = (_error: Error) => {}
    userStore.loadUser.mockReturnValueOnce(
      new Promise<void>((_resolve, reject) => {
        rejectCheck = reject
      }),
    )
    const store = useAuthStore()
    const navigation = navigate('/')
    apiMocks.signIn.mockResolvedValue({ user_id: 1 })
    userStore.loadUser.mockResolvedValue(undefined)

    await store.signIn({ email: 'user@example.com', password: 'password' })
    rejectCheck(new Error('Unauthorized'))
    await navigation

    expect(store.isAuth).toBe(true)
    const next = await navigate('/dashboard', { requireAuth: true })
    expect(next).toHaveBeenCalledWith()
    expect(userStore.loadUser).toHaveBeenCalledTimes(2)
  })

  it('does not restore authentication when an initial check completes after logout', async () => {
    let resolveCheck = () => {}
    userStore.loadUser.mockReturnValue(
      new Promise<void>((resolve) => {
        resolveCheck = resolve
      }),
    )
    const store = useAuthStore()
    const navigation = navigate('/')

    await store.logout()
    resolveCheck()
    await navigation

    expect(store.isAuth).toBe(false)
    await navigate('/sign-in')
    expect(userStore.loadUser).toHaveBeenCalledOnce()
  })
})
