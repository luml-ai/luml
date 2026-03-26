import type { NavigationGuardNext, RouteLocationNormalized } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useOrbitsStore } from '@/stores/orbits'
import { useOrganizationStore } from '@/stores/organization'
import { ROUTE_TO_TAB, TAB_TO_ROUTE } from '@/constants/orbit-navigation'

function toSetup(next: NavigationGuardNext, tab: string) {
  return next({ name: 'setup', query: { tab } })
}

export async function orbitMiddleware(
  to: RouteLocationNormalized,
  from: RouteLocationNormalized,
  next: NavigationGuardNext,
) {
  const authStore = useAuthStore()
  const orbitsStore = useOrbitsStore()
  const organizationStore = useOrganizationStore()

  const targetTab = ROUTE_TO_TAB[to.name as string] ?? 'registry'

  if (!authStore.isAuth) {
    return toSetup(next, targetTab)
  }

  if (!organizationStore.availableOrganizations.length) {
    try {
      await organizationStore.getAvailableOrganizations()
    } catch {
      return toSetup(next, targetTab)
    }
  }

  const urlOrgId = to.params.organizationId as string

  if (
    !organizationStore.currentOrganization ||
    organizationStore.currentOrganization.id !== urlOrgId
  ) {
    const hasAccess = organizationStore.availableOrganizations.some((o) => o.id === urlOrgId)
    if (hasAccess) {
      organizationStore.setCurrentOrganizationId(urlOrgId)
      orbitsStore.reset()
      await orbitsStore.loadOrbitsList(urlOrgId)
    } else {
      return toSetup(next, targetTab)
    }
  }

  if (!orbitsStore.orbitsList.length) {
    try {
      await orbitsStore.loadOrbitsList(urlOrgId)
    } catch (e) {
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
      name: to.name as string,
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
  const targetRoute = TAB_TO_ROUTE[tab] ?? 'orbit-registry'

  return next({
    name: targetRoute,
    params: { organizationId: orgId, id: firstOrbit.id },
  })
}
