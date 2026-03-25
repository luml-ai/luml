<template>
  <div class="page-header">
    <div class="page-header__left">
      <Folders :size="20" class="page-header__icon" />
      <h1 class="page-header__title">Registry</h1>
    </div>
    <d-button
      v-if="orbitsStore.currentOrbitDetails && authStore.isAuth"
      label="Create collection"
      @click="collectionsStore.showCreator()"
    >
      <template #icon>
        <Plus :size="14" />
      </template>
    </d-button>
  </div>

  <UiPageLoader v-if="orbitsStore.isLoadingOrbitDetails" />

  <OrbitEmptyState v-else-if="!orbitsStore.currentOrbitId" :cards="registryCards" />

  <CollectionsWelcome v-else-if="!loading && collectionsList.length === 0" />

  <div v-else>
    <CollectionsToolbar
      :types="typesQuery"
      :search="searchQuery"
      @update:search="onSearch"
      @update:types="setTypesQuery"
    />
    <div v-if="loading" class="loading-container">
      <Skeleton v-for="i in 10" :key="i" style="height: 146.5px" />
    </div>
    <CollectionsList v-else :list="collectionsList" @lazy-load="onLazyLoad" />

    <CollectionCreator
      :organization-id="orbitsStore.currentOrbitDetails?.organization_id"
      :orbit-id="orbitsStore.currentOrbitDetails?.id"
      :visible="collectionsStore.creatorVisible"
      @update:visible="updateCreatorVisible"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { Skeleton, useToast } from 'primevue'
import { useOrbitsStore } from '@/stores/orbits'
import { useAuthStore } from '@/stores/auth'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { useCollectionsStore } from '@/stores/collections'
import { useCollectionsList } from '@/hooks/useCollectionsList'
import { useDebounceFn } from '@vueuse/core'
import CollectionsList from '@/components/orbits/tabs/registry/CollectionsList.vue'
import CollectionCreator from '@/components/orbits/tabs/registry/CollectionCreator.vue'
import CollectionsToolbar from '@/components/orbits/tabs/registry/CollectionsToolbar.vue'
import CollectionsWelcome from '@/components/orbits/tabs/registry/CollectionsWelcome.vue'
import { Folders, Plus } from 'lucide-vue-next'
import OrbitEmptyState from '@/components/orbits/OrbitEmptyState.vue'
import UiPageLoader from '@/components/ui/UiPageLoader.vue'

const authStore = useAuthStore()
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

const registryCards = [
  {
    title: 'Registry',
    description:
      'Registry is a centralized hub for organizing and tracking ML models, experiments, and datasets — managing their versions and metadata throughout the entire lifecycle.',
  },
  {
    title: 'Overview',
    description:
      'Overview is a technical passport for any registry item — models, experiments, or datasets — containing metadata: name, date, size, content manifest, and tags for search and organization across collections.',
  },
]

function updateCreatorVisible(visible: boolean | undefined) {
  visible ? collectionsStore.showCreator() : collectionsStore.hideCreator()
}

function onSearch(value: string | undefined) {
  setSearchQuery(value?.trim() ?? '')
}

async function getFirstCollectionsPage() {
  if (!orbitsStore.currentOrbitDetails) return
  try {
    loading.value = true
    reset()
    setRequestInfo({
      organizationId: orbitsStore.currentOrbitDetails.organization_id,
      orbitId: orbitsStore.currentOrbitDetails.id,
    })
    await getInitialPage()
  } catch (e) {
    toast.add(simpleErrorToast('Failed to load collections'))
  } finally {
    loading.value = false
  }
}

watch(
  () => orbitsStore.currentOrbitDetails?.id,
  async (newId) => {
    if (!newId) return
    await getFirstCollectionsPage()
  },
  { immediate: true },
)

const debouncedFirstPage = useDebounceFn(getFirstCollectionsPage, 500)
watch([searchQuery, typesQuery], debouncedFirstPage)

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

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 25px;
  padding-top: 37px;
}

.page-header__left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.page-header__icon {
  width: 20px;
  height: 20px;
  color: var(--p-primary-color);
}

.page-header__title {
  font-weight: 500;
  line-height: 30px;
  letter-spacing: -0.48px;
}
</style>
