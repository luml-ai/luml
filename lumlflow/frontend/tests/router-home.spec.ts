import { describe, expect, it } from 'vitest'
import router from '@/router'
import { ROUTE_NAMES } from '@/router/router.const'

describe('home route', () => {
  it('opens the groups list when navigating by the home name', async () => {
    await router.push({ name: ROUTE_NAMES.HOME })
    expect(router.currentRoute.value.name).toBe(ROUTE_NAMES.EXPERIMENTS)
    expect(router.currentRoute.value.matched).toHaveLength(3)
  })

  it('keeps the root path on the groups list', async () => {
    await router.push({ name: ROUTE_NAMES.WORKSPACES })
    await router.push('/')
    expect(router.currentRoute.value.name).toBe(ROUTE_NAMES.EXPERIMENTS)
  })
})
