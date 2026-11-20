import { describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter, type RouteRecordRaw } from 'vue-router'
import appRouter from '@/router'

vi.mock('@/router/middlewares', () => ({ installMiddlewares: vi.fn() }))
vi.mock('@/pages/HomePage.vue', () => ({ default: { template: '<div />' } }))

const tasks = [
  'classification',
  'regression',
  'forecasting',
  'runtime',
  'prompt-fusion',
  'notebooks',
]

function testRoutes(routes: readonly RouteRecordRaw[]): RouteRecordRaw[] {
  return routes.map((route) => ({
    ...route,
    ...(route.component ? { component: { template: '<router-view />' } } : {}),
    ...(route.children ? { children: testRoutes(route.children) } : {}),
  })) as RouteRecordRaw[]
}

describe('express task routes', () => {
  it.each(tasks)('places %s under Express Tasks', (name) => {
    const route = appRouter.resolve({ name })
    const parent = appRouter.resolve('/express-tasks').matched[0]

    expect(route.path).toBe(`/express-tasks/${name}`)
    expect(route.matched[0]).toBe(parent)
    expect(route.matched).toHaveLength(2)
    expect(parent.components).toBeUndefined()
    expect(route.matched[1].components?.default).toBeDefined()
  })

  it.each([...tasks, 'prompt-fusion/edit'])(
    'redirects the existing %s link without losing its query or hash',
    async (task) => {
      const router = createRouter({
        history: createMemoryHistory(),
        routes: testRoutes(appRouter.options.routes),
      })
      await router.push(`/${task}?step=2&value=a&value=b#results`)

      expect(router.currentRoute.value.fullPath).toBe(
        `/express-tasks/${task}?step=2&value=a&value=b#results`,
      )
      expect(router.currentRoute.value.name).toBe(task.split('/')[0])
    },
  )

  it('preserves the optional prompt optimization mode and page restrictions', () => {
    const route = appRouter.resolve({ name: 'prompt-fusion', params: { mode: 'edit' } })

    expect(route.path).toBe('/express-tasks/prompt-fusion/edit')
    expect(route.params.mode).toBe('edit')
    expect(route.meta.mobileAvailable).toBe(false)
    expect(route.meta.showInvalidMessage).toBe(992)
    for (const name of ['classification', 'regression', 'forecasting', 'runtime']) {
      expect(appRouter.resolve({ name }).meta.showInvalidMessage).toBe(992)
    }
  })
})
