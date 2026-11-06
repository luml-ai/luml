<template>
  <UiPageLoader v-if="organizationStore.loading"></UiPageLoader>

  <div v-else-if="organizationStore.currentOrganization">
    <OrganizationLocked v-if="!hasPermission"></OrganizationLocked>
    <div v-else class="organization-page">
      <OrganizationInfo class="info"></OrganizationInfo>
      <OrganizationLimits class="limits"></OrganizationLimits>
      <OrganizationTabs></OrganizationTabs>
      <div class="views">
        <RouterView></RouterView>
      </div>
      <section v-if="canDeleteOrganization" class="danger-zone">
        <div>
          <div class="danger-zone-title">Delete organization</div>
          <p class="danger-zone-text">
            Permanently remove this organization with all its orbits and data. Remove the other
            members first.
          </p>
        </div>
        <OrganizationDelete></OrganizationDelete>
      </section>
    </div>
  </div>
  <div v-else class="title">Organization {{ route.params.id }} not found...</div>
</template>

<script setup lang="ts">
import { computed, onBeforeMount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useOrganizationStore } from '@/stores/organization'
import { useToast } from 'primevue'
import { OrganizationRoleEnum } from '@/components/organizations/organization.interfaces'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import OrganizationInfo from '@/components/organizations/OrganizationInfo.vue'
import OrganizationLimits from '@/components/organizations/OrganizationLimits.vue'
import OrganizationTabs from '@/components/organizations/OrganizationTabs.vue'
import OrganizationLocked from '@/components/organizations/OrganizationLocked.vue'
import OrganizationDelete from '@/components/organizations/OrganizationDelete.vue'
import { PermissionEnum } from '@/lib/api/api.interfaces'
import UiPageLoader from '@/components/ui/UiPageLoader.vue'
import type { ApiError } from '@/helpers/helpers'

const route = useRoute()
const router = useRouter()
const organizationStore = useOrganizationStore()
const toast = useToast()

const hasPermission = computed(() => {
  const userRole = organizationStore.availableOrganizations.find(
    (organization) => organization.id === organizationStore.currentOrganization?.id,
  )?.role
  if (!userRole || userRole === OrganizationRoleEnum.member) return false
  return true
})

const canDeleteOrganization = computed(
  () =>
    !!organizationStore.currentOrganization?.permissions?.organization?.includes(
      PermissionEnum.delete,
    ),
)

function isOrganizationUnavailable(organizationId: string) {
  const organizations = organizationStore.availableOrganizations
  if (organizationStore.availableOrganizationsRequest || !organizations.length) return false
  return !organizations.some((organization) => organization.id === organizationId)
}

async function init() {
  const idParam = route.params.id
  const organizationId = Array.isArray(idParam) ? idParam[0] : idParam
  if (!organizationId) {
    toast.add(simpleErrorToast('Organization not found'))
    return
  }
  try {
    if (organizationStore.availableOrganizationsRequest && organizationStore.currentOrganization) {
      await organizationStore.availableOrganizationsRequest
    }
    if (isOrganizationUnavailable(organizationId)) {
      await router.replace({ name: 'home' })
      return
    }
    if (organizationStore.currentOrganization?.id === organizationId) {
      if (hasPermission.value) await organizationStore.getOrganizationDetails(organizationId)
    } else {
      await organizationStore.switchOrganization(organizationId)
    }
  } catch (e: unknown) {
    const errorDetails = (e as ApiError)?.details
    toast.add(simpleErrorToast(errorDetails || 'Unable to retrieve organization data'))
  }
}

onBeforeMount(() => {
  init()
})

watch(
  () => organizationStore.currentOrganization?.id,
  async (id) => {
    if (!id || route.params.id === id) return

    await router.push({
      name: route.name,
      params: {
        ...route.params,
        id,
      },
    })

    init()
  },
)
</script>

<style scoped>
.organization-page {
  padding-top: 30px;
}
.info {
  margin-bottom: 24px;
}
.limits {
  margin-bottom: 44px;
}
.title {
  padding-top: 30px;
}
.views {
  padding-top: 24px;
}
.danger-zone {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 44px;
  padding: 24px 0;
  border-top: 1px solid var(--p-divider-border-color);
}
.danger-zone-title {
  font-weight: 500;
  margin-bottom: 4px;
}
.danger-zone-text {
  color: var(--p-text-muted-color);
}
</style>
