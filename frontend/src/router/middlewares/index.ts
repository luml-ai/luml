import type { Router } from 'vue-router'
import { loadLayoutMiddleware } from './LoadLayoutMiddleware'
import { authMiddleware } from './AuthMiddleware'
import { orbitMiddleware, setupGuard } from './OrbitMiddleware'

export const installMiddlewares = (router: Router) => {
  router.beforeEach(loadLayoutMiddleware)
  router.beforeEach(authMiddleware)
  router.beforeEach((to, from, next) => {
    if (to.matched.some((record) => record.meta.orbitMiddleware)) {
      return orbitMiddleware(to, from, next)
    }
    if (to.name === 'setup') {
      return setupGuard(to, from, next)
    }
    next()
  })
}
