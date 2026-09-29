import { describe, expect, it } from 'vitest'
import router from '@/router'

const ORGANIZATION_ID = '0199c50e-57ac-7823-b010-d5473e5eead1'
const ORBIT_ID = '0199c8cf-4d35-783b-9f81-cb3cec788074'

describe('flow routes', () => {
  it('shows the not-found page at the old address', () => {
    expect(router.resolve('/flow').name).toBe('404')
  })

  it('places the list under the orbit', () => {
    const route = router.resolve(`/organization/${ORGANIZATION_ID}/orbit/${ORBIT_ID}/flow`)

    expect(route.name).toBe('orbit-flow')
    expect(route.meta.requireAuth).toBe(true)
    expect(route.meta.orbitMiddleware).toBe(true)
  })

  it('places a session under the list, by its identifier', () => {
    const route = router.resolve(`/organization/${ORGANIZATION_ID}/orbit/${ORBIT_ID}/flow/k3j9x2`)

    expect(route.name).toBe('orbit-flow-session')
    expect(route.params.sessionId).toBe('k3j9x2')
    expect(route.meta.requireAuth).toBe(true)
  })
})
