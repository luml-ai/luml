<template>
  <div class="page-header">
    <div class="page-header__left">
      <GitBranch :size="20" class="page-header__icon" />
      <h1 class="page-header__title">Tracks</h1>
    </div>
    <d-button
      v-if="authStore.isAuth"
      label="Create track"
      @click="tracksStore.showCreator()"
    >
      <template #icon>
        <Plus :size="14" />
      </template>
    </d-button>
  </div>

  <div v-if="loading" class="loading-container">
    <Skeleton v-for="i in 10" :key="i" style="height: 146.5px" />
  </div>

  <TracksWelcome v-else-if="tracksList.length === 0" />

  <div v-else>
    <TracksToolbar
      :types="typesQuery"
      :search="searchQuery"
      @update:search="onSearch"
      @update:types="setTypesQuery"
    />
    <TracksList :list="tracksList" @lazy-load="onLazyLoad" />
  </div>

  <TrackCreator
    :organization-id="route.params.organizationId as string"
    :orbit-id="route.params.id as string"
    :visible="tracksStore.creatorVisible"
    @update:visible="updateCreatorVisible"
  />
</template>

<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Skeleton, useToast } from 'primevue'
import { useAuthStore } from '@/stores/auth'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { useTracksStore } from '@/stores/tracks'
import { useTracksList } from '@/hooks/useTracksList'
import { useDebounceFn } from '@vueuse/core'
import TracksList from '@/components/orbits/tabs/tracks/TracksList.vue'
import TrackCreator from '@/components/orbits/tabs/tracks/TrackCreator.vue'
import TracksToolbar from '@/components/orbits/tabs/tracks/TracksToolbar.vue'
import TracksWelcome from '@/components/orbits/tabs/tracks/TracksWelcome.vue'
import { GitBranch, Plus } from 'lucide-vue-next'

const route = useRoute()
const authStore = useAuthStore()
const tracksStore = useTracksStore()
const toast = useToast()

const {
  setRequestInfo,
  getInitialPage,
  tracksList,
  reset,
  searchQuery,
  setSearchQuery,
  onLazyLoad,
  typesQuery,
  setTypesQuery,
} = useTracksList()

const loading = ref(false)

function updateCreatorVisible(visible: boolean | undefined) {
  visible ? tracksStore.showCreator() : tracksStore.hideCreator()
}

function onSearch(value: string | undefined) {
  setSearchQuery(value?.trim() ?? '')
}

async function getFirstTracksPage() {
  const organizationId = route.params.organizationId as string
  const orbitId = route.params.id as string
  if (!organizationId || !orbitId) return

  try {
    loading.value = true
    reset()
    setRequestInfo({ organizationId, orbitId })
    await getInitialPage()
  } catch (e) {
    toast.add(simpleErrorToast('Failed to load tracks'))
  } finally {
    loading.value = false
  }
}

watch(
  () => route.params.id,
  async (newId) => {
    if (!newId) return
    await getFirstTracksPage()
  },
  { immediate: true },
)

const debouncedFirstPage = useDebounceFn(getFirstTracksPage, 500)
watch([searchQuery, typesQuery], debouncedFirstPage)

onUnmounted(() => {
  tracksStore.reset()
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
