<template>
  <div class="page-header">
    <div class="page-header__left">
      <Folders :size="20" class="page-header__icon" />
      <h1 class="page-header__title">Registry</h1>
    </div>
    <d-button
      v-if="authStore.isAuth"
      label="Create collection"
      @click="collectionsStore.showCreator()"
    >
      <template #icon>
        <Plus :size="14" />
      </template>
    </d-button>
  </div>

  <div v-if="loading" class="loading-container">
    <Skeleton v-for="i in 10" :key="i" style="height: 146.5px" />
  </div>

  <CollectionsWelcome v-else-if="collectionsList.length === 0" />

  <div v-else>
    <CollectionsToolbar
      :types="typesQuery"
      :search="searchQuery"
      @update:search="onSearch"
      @update:types="setTypesQuery"
    />
    <CollectionsList :list="collectionsList" @lazy-load="onLazyLoad" />
  </div>

  <CollectionCreator
    :organization-id="organizationId"
    :orbit-id="orbitId"
    :visible="collectionsStore.creatorVisible"
    @update:visible="updateCreatorVisible"
  />
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Skeleton, useToast } from 'primevue'
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

const route = useRoute()
const authStore = useAuthStore()
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

const organizationId = computed(() => route.params.organizationId as string)
const orbitId = computed(() => route.params.id as string)

function updateCreatorVisible(visible: boolean | undefined) {
  visible ? collectionsStore.showCreator() : collectionsStore.hideCreator()
}

function onSearch(value: string | undefined) {
  setSearchQuery(value?.trim() ?? '')
}

async function getFirstCollectionsPage() {
  if (!organizationId.value || !orbitId.value) return

  try {
    loading.value = true
    reset()
    setRequestInfo({ organizationId: organizationId.value, orbitId: orbitId.value })
    await getInitialPage()
  } catch (e) {
    toast.add(simpleErrorToast('Failed to load collections'))
  } finally {
    loading.value = false
  }
}

watch(
  () => route.params.id,
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
