import type { NavigationGuardNext, RouteLocationNormalized } from 'vue-router'
import { z } from 'zod'

const ID_PARAMS = ['organizationId', 'id', 'collectionId', 'artifactId', 'trackId', 'deploymentId']

const isId = (value: unknown) => typeof value === 'string' && z.guid().safeParse(value).success

export function routeIdsMiddleware(
  to: RouteLocationNormalized,
  _from: RouteLocationNormalized,
  next: NavigationGuardNext,
) {
  const hasInvalidId = ID_PARAMS.some((param) => param in to.params && !isId(to.params[param]))
  if (!hasInvalidId) return next()

  return next({
    name: '404',
    params: { pathMatch: to.path.substring(1).split('/') },
    query: to.query,
    hash: to.hash,
  })
}
