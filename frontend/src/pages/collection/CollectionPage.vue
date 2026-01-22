<template>
  <div>
    <UiPageLoader v-if="loading"></UiPageLoader>

    <div v-else-if="collectionsStore.currentCollection" class="page-content">
      <CollectionBreadcrumb></CollectionBreadcrumb>
      <RouterView></RouterView>
    </div>

    <Ui404 v-else></Ui404>
  </div>
</template>

<script setup lang="ts">
import { onBeforeMount, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useCollectionsStore } from '@/stores/collections'
import { useOrbitsStore } from '@/stores/orbits'
import { useToast } from 'primevue'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { useOrganizationStore } from '@/stores/organization'
import Ui404 from '@/components/ui/Ui404.vue'
import UiPageLoader from '@/components/ui/UiPageLoader.vue'
import CollectionBreadcrumb from '@/components/orbits/tabs/registry/collection/CollectionBreadcrumb.vue'

const route = useRoute()
const router = useRouter()
const organizationStore = useOrganizationStore()
const orbitsStore = useOrbitsStore()
const collectionsStore = useCollectionsStore()
const toast = useToast()

const loading = ref(true)

function ensureString(param: string | string[] | undefined): string {
  if (Array.isArray(param)) return param[0]
  if (!param) throw new Error('Missing route param')
  return param
}

async function init(organizationId: string) {
  try {
    loading.value = true

    const orbitId = ensureString(route.params.id)
    const collectionId = ensureString(route.params.collectionId)

    if (orbitsStore.currentOrbitDetails?.id !== orbitId) {
      const details = await orbitsStore.getOrbitDetails(organizationId, orbitId)
      orbitsStore.setCurrentOrbitDetails(details)
    }
    await collectionsStore.setCurrentCollection(collectionId)
  } catch (e) {
    toast.add(simpleErrorToast('Failed to load collection data'))
  } finally {
    loading.value = false
  }
}

watch(
  () => organizationStore.currentOrganization?.id,
  async (id) => {
    if (!id || route.params.organizationId === id) return
    await router.push({ name: 'orbits', params: { organizationId: id } })
  },
)

onBeforeMount(() => {
  const organizationId = ensureString(route.params.organizationId)
  init(organizationId)
})

onUnmounted(() => {
  collectionsStore.resetCurrentCollection()
})
</script>

<style scoped>
.loader-wrapper {
  width: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}
.page-content {
  padding-top: 18px;
}

.table {
  flex: 1 1 auto;
  margin-bottom: 16px;
}

.navigate-button {
  align-self: flex-start;
  margin-left: -88px;
}
</style>
