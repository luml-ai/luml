import type { NavigationGuardNext, RouteLocationNormalized } from 'vue-router'
import { useOrbitsStore } from '@/stores/orbits'

export function orbitMiddleware(
  to: RouteLocationNormalized,
  from: RouteLocationNormalized,
  next: NavigationGuardNext,
) {
  const orbitsStore = useOrbitsStore()
  const orbitId = Array.isArray(to.query.orbitId) ? to.query.orbitId[0] : (to.query.orbitId ?? null)

  orbitsStore.setCurrentOrbitId(orbitId as string | null)
  next()
}
