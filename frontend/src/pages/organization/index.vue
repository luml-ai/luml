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

async function init() {
  const idParam = route.params.id
  const organizationId = Array.isArray(idParam) ? idParam[0] : idParam
  if (!organizationId) {
    toast.add(simpleErrorToast('Organization not found'))
    return
  }
  try {
    organizationStore.resetCurrentOrganization()
    organizationStore.setCurrentOrganizationId(organizationId)
    organizationStore.getOrganizationDetails(organizationId)
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
</style>
