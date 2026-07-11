<template>
  <div>
    <div v-if="initialLoading" class="loading-container">
      <Skeleton style="height: 27.5px" />
      <Skeleton v-for="i in 10" :key="i" style="height: 146.5px" />
    </div>

    <CollectionsWelcome v-else-if="isEmpty" />

    <div v-else>
      <CollectionsToolbar
        :types="typesQuery"
        :search="searchQuery"
        @update:search="onSearch"
        @update:types="setTypesQuery"
      />
      <div v-if="isLoading" class="loading-container">
        <Skeleton v-for="i in 10" :key="i" style="height: 146.5px" />
      </div>
      <CollectionsList
        v-else-if="collectionsList.length"
        :list="collectionsList"
        @lazy-load="onLazyLoad"
      />
      <div v-else class="empty-message">Collections not found...</div>
    </div>

    <CollectionCreator
      :organization-id="organizationId"
      :orbit-id="orbitId"
      :visible="collectionsStore.creatorVisible"
      @update:visible="updateCreatorVisible"
    />
  </div>
</template>

<script setup lang="ts">
import { useCollectionsList } from '@/hooks/useCollectionsList'
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Skeleton, useToast } from 'primevue'
import { useCollectionsStore } from '@/stores/collections'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { watch } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import CollectionsWelcome from '@/components/orbits/tabs/registry/CollectionsWelcome.vue'
import CollectionsToolbar from '@/components/orbits/tabs/registry/CollectionsToolbar.vue'
import CollectionsList from '@/components/orbits/tabs/registry/CollectionsList.vue'
import CollectionCreator from '@/components/orbits/tabs/registry/CollectionCreator.vue'

const route = useRoute()
const toast = useToast()
const collectionsStore = useCollectionsStore()

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
  isLoading,
} = useCollectionsList()

const initialLoading = ref(true)

const isEmpty = ref(true)

const organizationId = computed(() => route.params.organizationId as string)
const orbitId = computed(() => route.params.id as string)

function onSearch(value: string | undefined) {
  setSearchQuery(value?.trim() ?? '')
}

function updateCreatorVisible(visible: boolean | undefined) {
  if (visible) {
    collectionsStore.showCreator()
  } else {
    collectionsStore.hideCreator()
  }
}

async function getFirstCollectionsPage() {
  if (!organizationId.value || !orbitId.value) return

  try {
    reset()
    setRequestInfo({ organizationId: organizationId.value, orbitId: orbitId.value })
    await getInitialPage()
  } catch {
    toast.add(simpleErrorToast('Failed to load collections'))
  } finally {
    initialLoading.value = false
  }
}

const debouncedFirstPage = useDebounceFn(getFirstCollectionsPage, 500)

watch([searchQuery, typesQuery], debouncedFirstPage)

watch(
  () => route.params.id,
  async (newId) => {
    if (!newId) return
    await getFirstCollectionsPage()
  },
  { immediate: true },
)

watch(collectionsList, (list) => {
  if (list.length > 0) {
    isEmpty.value = false
  }
})
</script>

<style scoped>
.loading-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.empty-message {
  text-align: center;
  padding: 40px;
  color: var(--p-text-muted-color);
  font-size: 14px;
}
</style>
