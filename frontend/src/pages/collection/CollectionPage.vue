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
import Ui404 from '@/components/ui/Ui404.vue'
import UiPageLoader from '@/components/ui/UiPageLoader.vue'
import { useOrganizationStore } from '@/stores/organization'
import CollectionBreadcrumb from '@/components/orbits/tabs/registry/collection/CollectionBreadcrumb.vue'
import { useModelsStore } from '@/stores/models'

const route = useRoute()
const router = useRouter()
const organizationStore = useOrganizationStore()
const orbitsStore = useOrbitsStore()
const collectionsStore = useCollectionsStore()
const toast = useToast()
const modelsStore = useModelsStore()

const loading = ref(true)

async function init(organizationId: number) {
  try {
    loading.value = true
    if (typeof route.params.id !== 'string' || typeof route.params.collectionId !== 'string')
      throw new Error('Incorrect route data')

    if (orbitsStore.currentOrbitDetails?.id !== +route.params.id) {
      const details = await orbitsStore.getOrbitDetails(organizationId, +route.params.id)
      orbitsStore.setCurrentOrbitDetails(details)
    }
    await collectionsStore.loadCollections()
    const modelsList = await modelsStore.getModelsList()
    modelsStore.setModelsList(modelsList)
    collectionsStore.setCurrentCollection(+route.params.collectionId)
  } catch {
    toast.add(simpleErrorToast('Failed to load collection data'))
  } finally {
    loading.value = false
  }
}

watch(
  () => organizationStore.currentOrganization?.id,
  async (id) => {
    if (!id || +route.params.organizationId === id) return
    await router.push({ name: 'orbits', params: { organizationId: id } })
  },
)

onBeforeMount(() => {
  init(+route.params.organizationId)
})

onUnmounted(() => {
  collectionsStore.resetCurrentCollection()
  modelsStore.resetList()
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
