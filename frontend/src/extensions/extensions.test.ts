import { describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent } from 'vue'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import { installExtensions } from '.'

const Empty = defineComponent({ render: () => null })

function createTestRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/parent/:id', name: 'parent', component: Empty, children: [] }],
  })
}

describe('installExtensions', () => {
  it('registers top-level routes', () => {
    const router = createTestRouter()
    installExtensions(createApp(Empty), router, createPinia(), [
      { routes: [{ path: '/extra', name: 'extra', component: Empty }] },
    ])
    expect(router.resolve('/extra').name).toBe('extra')
  })

  it('registers child routes under their named parent', () => {
    const router = createTestRouter()
    installExtensions(createApp(Empty), router, createPinia(), [
      { routes: [{ parent: 'parent', route: { path: 'child', name: 'child', component: Empty } }] },
    ])
    const resolved = router.resolve('/parent/1/child')
    expect(resolved.name).toBe('child')
    expect(resolved.matched.map((record) => record.name)).toEqual(['parent', 'child'])
  })

  it('throws when a child route names an unknown parent', () => {
    const router = createTestRouter()
    expect(() =>
      installExtensions(createApp(Empty), router, createPinia(), [
        { routes: [{ parent: 'missing', route: { path: 'child', component: Empty } }] },
      ]),
    ).toThrow('Extension route parent "missing" is not a registered route name')
  })

  it('calls install with the app, router and pinia instances', () => {
    const app = createApp(Empty)
    const router = createTestRouter()
    const pinia = createPinia()
    const install = vi.fn()
    installExtensions(app, router, pinia, [{ install }])
    expect(install).toHaveBeenCalledWith(app, router, pinia)
  })

  it('leaves the router untouched when there are no extensions', () => {
    const router = createTestRouter()
    const routesBefore = router.getRoutes().map((record) => record.name)
    installExtensions(createApp(Empty), router, createPinia(), [])
    expect(router.getRoutes().map((record) => record.name)).toEqual(routesBefore)
  })
})
