import type { Router } from 'vue-router'
import { loadLayoutMiddleware } from './LoadLayoutMiddleware'
import { authMiddleware } from './AuthMiddleware'
import { orbitMiddleware } from './OrbitMiddleware'

export const installMiddlewares = (router: Router) => {
  router.beforeEach(loadLayoutMiddleware)
  router.beforeEach(authMiddleware)
  router.beforeEach((to, from, next) => {
    if (to.meta.orbitMiddleware) {
      return orbitMiddleware(to, from, next)
    }
    next()
  })
}
