import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { RouteLocationNormalized } from 'vue-router'
import router from '@/router'
import { authMiddleware } from '../AuthMiddleware'

const auth = vi.hoisted(() => ({ isAuth: false, checkIsLoggedIn: vi.fn() }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => auth }))
vi.mock('@/pages/HomePage.vue', () => ({ default: {} }))
vi.mock('@/router/middlewares', () => ({ installMiddlewares: vi.fn() }))

const protectedRoutes = router.getRoutes().flatMap((record) => {
  if (!record.name) return []
  const params = Object.fromEntries(
    [...record.path.matchAll(/:(\w+)/g)].map((match) => [match[1], `${match[1]}-1`]),
  )
  const route = router.resolve({
    name: record.name,
    params,
    query: { tab: 'details', search: 'a b' },
    hash: '#selected',
  })
  return route.meta.requireAuth ? [route] : []
})

describe('protected deep links', () => {
  beforeEach(() => {
    auth.isAuth = false
    auth.checkIsLoggedIn.mockResolvedValue(undefined)
  })

  it.each(protectedRoutes)('preserves the complete target of $name', async (to) => {
    const next = vi.fn()

    await authMiddleware(to as RouteLocationNormalized, router.currentRoute.value, next)

    expect(next).toHaveBeenCalledExactlyOnceWith({
      name: 'sign-in',
      query: { redirect: to.fullPath },
    })
  })

  it('preserves the target if the session check throws', async () => {
    auth.checkIsLoggedIn.mockRejectedValue(new Error('Network unavailable'))
    const next = vi.fn()
    const to = protectedRoutes[0]

    await authMiddleware(to as RouteLocationNormalized, router.currentRoute.value, next)

    expect(next).toHaveBeenCalledExactlyOnceWith({
      name: 'sign-in',
      query: { redirect: to.fullPath },
    })
  })

  it('allows authenticated users through without another session check', async () => {
    auth.isAuth = true
    const next = vi.fn()

    await authMiddleware(
      protectedRoutes[0] as RouteLocationNormalized,
      router.currentRoute.value,
      next,
    )

    expect(next).toHaveBeenCalledExactlyOnceWith()
    expect(auth.checkIsLoggedIn).not.toHaveBeenCalled()
  })
})
