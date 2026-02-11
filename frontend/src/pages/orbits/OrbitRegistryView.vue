<template>
  <div>
    <CollectionsToolbar
      :types="typesQuery"
      :search="searchQuery"
      @update:search="onSearch"
      @update:types="setTypesQuery"
    ></CollectionsToolbar>
    <div v-if="loading" class="loading-container">
      <Skeleton v-for="i in 10" :key="i" style="height: 146.5px" />
    </div>
    <CollectionsWelcome v-else-if="collectionsList.length === 0" />
    <CollectionsList v-else :list="collectionsList" @lazy-load="onLazyLoad"></CollectionsList>
  </div>
  <CollectionCreator
    :organization-id="orbitsStore.currentOrbitDetails!.organization_id"
    :orbit-id="orbitsStore.currentOrbitDetails!.id"
    :visible="collectionsStore.creatorVisible"
    @update:visible="updateCreatorVisible"
  />
</template>

<script setup lang="ts">
import { onBeforeMount, onUnmounted, ref, watch } from 'vue'
import { Skeleton, useToast } from 'primevue'
import { useOrbitsStore } from '@/stores/orbits'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { useCollectionsStore } from '@/stores/collections'
import { useCollectionsList } from '@/hooks/useCollectionsList'
import { useDebounceFn } from '@vueuse/core'
import CollectionsList from '@/components/orbits/tabs/registry/CollectionsList.vue'
import CollectionCreator from '@/components/orbits/tabs/registry/CollectionCreator.vue'
import CollectionsToolbar from '@/components/orbits/tabs/registry/CollectionsToolbar.vue'
import CollectionsWelcome from '@/components/orbits/tabs/registry/CollectionsWelcome.vue'

const orbitsStore = useOrbitsStore()
const collectionsStore = useCollectionsStore()
const toast = useToast()
const {
  setRequestInfo,
  getInitialPage,
  collectionsList,
  reset,
  searchQuery,
  setSearchQuery,
  onLazyLoad,
  typesQuery,
  setTypesQuery,
} = useCollectionsList()

const loading = ref(false)

function updateCreatorVisible(visible: boolean | undefined) {
  visible ? collectionsStore.showCreator() : collectionsStore.hideCreator()
}

function onSearch(value: string | undefined) {
  setSearchQuery(value?.trim() ?? '')
}

async function getFirstCollectionsPage() {
  try {
    loading.value = true
    reset()
    setRequestInfo({
      organizationId: orbitsStore.currentOrbitDetails!.organization_id,
      orbitId: orbitsStore.currentOrbitDetails!.id,
    })
    await getInitialPage()
  } catch (e) {
    toast.add(simpleErrorToast('Failed to load collections'))
  } finally {
    loading.value = false
  }
}

const debouncedFirstPage = useDebounceFn(getFirstCollectionsPage, 500)

watch([searchQuery, typesQuery], debouncedFirstPage)

onBeforeMount(async () => {
  await getFirstCollectionsPage()
})

onUnmounted(() => {
  collectionsStore.reset()
})
</script>

<style scoped>
.loading-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
}
</style>
