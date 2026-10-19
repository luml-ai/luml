import type { NavigationGuardNext, RouteLocationNormalized } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useOrbitsStore } from '@/stores/orbits'
import { useOrganizationStore } from '@/stores/organization'
import {
  ORBIT_TAB_ROUTES,
  RESOURCE_ROUTE_TO_TAB_ROUTE,
  ROUTE_TO_TAB,
  TAB_TO_ROUTE,
} from '@/constants/orbit-navigation'

function toSetup(next: NavigationGuardNext, tab: string) {
  return next({ name: 'setup', query: { tab } })
}

function orbitTabRoute(routeName: string) {
  if (ORBIT_TAB_ROUTES.includes(routeName)) return routeName
  return RESOURCE_ROUTE_TO_TAB_ROUTE[routeName] ?? TAB_TO_ROUTE.registry
}

export async function orbitMiddleware(
  to: RouteLocationNormalized,
  from: RouteLocationNormalized,
  next: NavigationGuardNext,
) {
  const authStore = useAuthStore()
  const orbitsStore = useOrbitsStore()
  const organizationStore = useOrganizationStore()

  const tabRoute = orbitTabRoute(to.name as string)
  const targetTab = ROUTE_TO_TAB[tabRoute] ?? 'registry'

  if (!authStore.isAuth) {
    return toSetup(next, targetTab)
  }

  if (
    !organizationStore.availableOrganizations.length ||
    organizationStore.availableOrganizationsRequest
  ) {
    try {
      await organizationStore.getAvailableOrganizations()
    } catch {
      return toSetup(next, targetTab)
    }
  }

  const urlOrgId = to.params.organizationId as string

  if (!organizationStore.availableOrganizations.some((org) => org.id === urlOrgId)) {
    return toSetup(next, targetTab)
  }

  if (organizationStore.currentOrganization?.id !== urlOrgId) {
    try {
      await organizationStore.switchOrganization(urlOrgId)
    } catch {
      return toSetup(next, targetTab)
    }
  } else if (!orbitsStore.orbitsList.length) {
    try {
      await orbitsStore.loadOrbitsList(urlOrgId)
    } catch {
      return toSetup(next, targetTab)
    }
  }

  const orbitId = to.params.id as string
  const orbitExists = orbitsStore.orbitsList.some((o) => o.id === orbitId)

  if (orbitExists) {
    orbitsStore.setCurrentOrbitId(orbitId, urlOrgId)
    return next()
  }

  const firstOrbit = orbitsStore.orbitsList[0]
  if (firstOrbit) {
    return next({
      name: tabRoute,
      params: { organizationId: urlOrgId, id: firstOrbit.id },
    })
  }

  return toSetup(next, targetTab)
}

export async function setupGuard(
  to: RouteLocationNormalized,
  from: RouteLocationNormalized,
  next: NavigationGuardNext,
) {
  const authStore = useAuthStore()
  const organizationStore = useOrganizationStore()
  const orbitsStore = useOrbitsStore()

  if (!authStore.isAuth || !organizationStore.currentOrganization) {
    return next()
  }

  const orgId = organizationStore.currentOrganization.id

  if (!orbitsStore.orbitsList.length) {
    try {
      await orbitsStore.loadOrbitsList(orgId)
    } catch {
      return next()
    }
  }

  const firstOrbit = orbitsStore.orbitsList[0]
  if (!firstOrbit) {
    return next()
  }

  const tab = (to.query.tab as string) ?? 'registry'
  const targetRoute = TAB_TO_ROUTE[tab] ?? 'orbit-collections'

  return next({
    name: targetRoute,
    params: { organizationId: orgId, id: firstOrbit.id },
  })
}
