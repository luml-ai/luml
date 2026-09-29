import type { NavigationGuardNext, RouteLocationNormalized } from 'vue-router'
import { describe, expect, it, vi } from 'vitest'
import { orbitMiddleware } from './OrbitMiddleware'

vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ isAuth: false }) }))
vi.mock('@/stores/orbits', () => ({ useOrbitsStore: () => ({}) }))
vi.mock('@/stores/organization', () => ({ useOrganizationStore: () => ({}) }))

describe('orbitMiddleware', () => {
  it.each(['orbit-flow', 'orbit-flow-session'])(
    'sends a user who is not signed in from %s to the Flow tab of the setup page',
    async (name) => {
      const next = vi.fn() as NavigationGuardNext
      const to = { name, params: {} } as unknown as RouteLocationNormalized

      await orbitMiddleware(to, {} as RouteLocationNormalized, next)

      expect(next).toHaveBeenCalledWith({ name: 'setup', query: { tab: 'flow' } })
    },
  )
})
