<template>
  <div class="content">
    <UiPageLoader v-if="loading"></UiPageLoader>

    <div v-else-if="organizationStore.currentOrganization">
      <OrbitsListHeader
        class="header"
        :create-available="createAvailable"
        @create-new="showCreator = true"
      ></OrbitsListHeader>
      <OrbitsList
        :create-available="createAvailable"
        :orbits="orbitsStore.orbitsList"
        @create-new="showCreator = true"
      ></OrbitsList>
      <OrbitCreator v-model:visible="showCreator"></OrbitCreator>
    </div>

    <Ui404 v-else></Ui404>
  </div>
</template>

<script setup lang="ts">
import { useOrbitsStore } from '@/stores/orbits'
import { computed, onBeforeMount, ref, watch } from 'vue'
import { useOrganizationStore } from '@/stores/organization'
import { useToast } from 'primevue'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import Ui404 from '@/components/ui/Ui404.vue'
import OrbitsListHeader from '@/components/orbits/OrbitsListHeader.vue'
import OrbitsList from '@/components/orbits/OrbitsList.vue'
import OrbitCreator from '@/components/orbits/creator/OrbitCreator.vue'
import UiPageLoader from '@/components/ui/UiPageLoader.vue'
import { useRoute, useRouter } from 'vue-router'
import { PermissionEnum } from '@/lib/api/DataforceApi.interfaces'

const organizationStore = useOrganizationStore()
const orbitsStore = useOrbitsStore()
const toast = useToast()
const route = useRoute()
const router = useRouter()

const loading = ref(false)
const showCreator = ref(false)

const createAvailable = computed(
  () =>
    !!organizationStore.currentOrganization?.permissions?.orbit?.includes(PermissionEnum.create),
)

async function loadOrbits(organizationId: number, skipHideLoading = false) {
  try {
    loading.value = true
    await orbitsStore.loadOrbitsList(organizationId)
  } catch (e: any) {
    toast.add(simpleErrorToast(e?.message || 'Failed to load orbits'))
  } finally {
    if (skipHideLoading) return
    loading.value = false
  }
}

watch(
  () => organizationStore.currentOrganization?.id,
  async (id) => {
    if (!id || +route.params.organizationId === id) return

    await router.push({ name: route.name, params: { organizationId: id } })
    loadOrbits(id)
  },
)

onBeforeMount(async () => {
  try {
    await loadOrbits(+route.params.organizationId, true)
    await organizationStore.getOrganizationDetails(+route.params.organizationId)
  } catch (e: any) {
    console.error(e?.response?.data?.detail, e?.message)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.content {
  padding-top: 32px;
  box-sizing: border-box;
}
.header {
  margin-bottom: 44px;
}
</style>
