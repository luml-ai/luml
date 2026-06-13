<template>
  <div>
    <div v-if="initialLoading" class="loading-container">
      <Skeleton style="height: 27.5px" />
      <Skeleton v-for="i in 10" :key="i" style="height: 102px" />
    </div>

    <TracksWelcome v-else-if="isEmpty" />

    <div v-else>
      <TracksToolbar
        :search="searchQuery"
        :types="typesQuery"
        @update:search="onSearch"
        @update:types="setTypesQuery"
      />
      <div v-if="isLoading" class="loading-container">
        <Skeleton v-for="i in 10" :key="i" style="height: 102px" />
      </div>

      <TracksList v-else-if="tracksList.length" :list="tracksList" @lazy-load="onLazyLoad" />

      <div v-else class="empty-message">Tracks not found...</div>
    </div>

    <TracksCreator />

    <TrackEditor />
  </div>
</template>

<script setup lang="ts">
import { useTracksList } from '@/hooks/useTracksList'
import { ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useDebounceFn } from '@vueuse/core'
import { Skeleton, useToast } from 'primevue'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import TracksToolbar from '@/components/tracks/TracksToolbar.vue'
import TracksCreator from '@/components/tracks/TracksCreator.vue'
import TrackEditor from '@/components/tracks/TrackEditor.vue'
import TracksList from '@/components/tracks/TracksList.vue'
import TracksWelcome from '@/components/tracks/TracksWelcome.vue'

const route = useRoute()
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
  isLoading,
} = useTracksList()

const initialLoading = ref(true)

const isEmpty = ref(true)

const organizationId = computed(() => route.params.organizationId as string)
const orbitId = computed(() => route.params.id as string)

function onSearch(value: string | undefined) {
  setSearchQuery(value?.trim() ?? '')
}

async function getFirstPage() {
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

const debouncedFirstPage = useDebounceFn(getFirstPage, 500)

watch([searchQuery, typesQuery], debouncedFirstPage)

watch(
  () => route.params.id,
  async (newId) => {
    if (!newId) return
    await getFirstPage()
  },
  { immediate: true },
)

watch(tracksList, (list) => {
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
