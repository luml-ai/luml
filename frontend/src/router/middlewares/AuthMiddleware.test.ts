import type { NavigationGuardNext, RouteLocationNormalized } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const authStore = {
  isAuth: false,
  checkIsLoggedIn: vi.fn(),
}

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => authStore,
}))

import { authMiddleware } from './AuthMiddleware'

const from = {} as RouteLocationNormalized

describe('authMiddleware invitation redirect', () => {
  beforeEach(() => {
    authStore.isAuth = false
    authStore.checkIsLoggedIn.mockReset()
  })

  it('redirects unauthenticated invitation visitors to sign in', async () => {
    const next = vi.fn() as NavigationGuardNext
    const to = {
      fullPath: '/invitations',
      meta: { requireAuth: true, redirectToSignIn: true },
    } as RouteLocationNormalized

    await authMiddleware(to, from, next)

    expect(next).toHaveBeenCalledOnce()
    expect(next).toHaveBeenCalledWith({
      name: 'sign-in',
      query: { redirect: '/invitations' },
    })
  })

  it('allows authenticated invitation visitors through', async () => {
    authStore.isAuth = true
    const next = vi.fn() as NavigationGuardNext
    const to = {
      fullPath: '/invitations',
      meta: { requireAuth: true, redirectToSignIn: true },
    } as RouteLocationNormalized

    await authMiddleware(to, from, next)

    expect(next).toHaveBeenCalledOnce()
    expect(next).toHaveBeenCalledWith()
    expect(authStore.checkIsLoggedIn).not.toHaveBeenCalled()
  })
})
