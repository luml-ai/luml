import type { NavigationGuardNext, RouteLocationNormalized } from 'vue-router'
import { describe, expect, it, vi } from 'vitest'
import { routeIdsMiddleware } from './RouteIdsMiddleware'

const ORGANIZATION_ID = '0199c50e-57ac-7823-b010-d5473e5eead1'
const ORBIT_ID = '0199c8cf-4d35-783b-9f81-cb3cec788074'
const COLLECTION_ID = '01a08aeb-464e-72a5-bbf3-7f6b36878342'
const from = {} as RouteLocationNormalized

function navigate(path: string, params: Record<string, string>) {
  const next = vi.fn() as NavigationGuardNext
  const to = {
    path,
    params,
    query: { tab: 'overview' },
    hash: '#top',
  } as unknown as RouteLocationNormalized
  routeIdsMiddleware(to, from, next)
  return next
}

describe('routeIdsMiddleware', () => {
  it('lets routes with valid ids through', () => {
    const next = navigate(`/organization/${ORGANIZATION_ID}/orbit/${ORBIT_ID}`, {
      organizationId: ORGANIZATION_ID,
      id: ORBIT_ID,
    })

    expect(next).toHaveBeenCalledWith()
  })

  it('lets routes without id params through', () => {
    const next = navigate('/prompt-fusion/edit', { mode: 'edit' })

    expect(next).toHaveBeenCalledWith()
  })

  it.each(['organizationId', 'id', 'collectionId', 'artifactId', 'trackId', 'deploymentId'])(
    'shows the 404 page when %s is not a UUID',
    (param) => {
      const params = {
        organizationId: ORGANIZATION_ID,
        id: ORBIT_ID,
        collectionId: COLLECTION_ID,
        [param]: 'abc',
      }
      const path = `/organization/${params.organizationId}/orbit/${params.id}/collection/${params.collectionId}`

      const next = navigate(path, params)

      expect(next).toHaveBeenCalledWith({
        name: '404',
        params: { pathMatch: path.substring(1).split('/') },
        query: { tab: 'overview' },
        hash: '#top',
      })
    },
  )
})
