<template>
  <div class="page-header">
    <div class="page-header__left">
      <Library :size="20" class="page-header__icon" />
      <h1 class="page-header__title">Tracks</h1>
    </div>
    <d-button
      v-if="canCreate"
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

  <div v-else-if="tracksList.length === 0" class="welcome">
    <Library :size="35" color="var(--p-primary-color)" />
    <h3 class="welcome__label">Get started with Tracks</h3>
    <div class="welcome__text">
      <p>Create named artifact registries with versioned entries and lifecycle stages.</p>
      <p>Start by creating your first track.</p>
    </div>
    <d-button
      v-if="canCreate"
      label="Create track"
      @click="tracksStore.showCreator()"
    >
      <template #icon>
        <Plus :size="14" />
      </template>
    </d-button>
  </div>

  <div v-else>
    <div class="toolbar">
      <IconField>
        <InputText
          v-model="searchQuery"
          size="small"
          placeholder="Search"
        />
        <InputIcon>
          <Search :size="12" />
        </InputIcon>
      </IconField>
      <Select
        v-model="typeFilter"
        :options="TRACK_TYPE_OPTIONS"
        option-label="label"
        option-value="value"
        size="small"
        placeholder="Filter by type"
        showClear
        :pt="{ root: { style: 'width: 230px;' } }"
      />
    </div>
    <VirtualScroller
      :items="filteredTracks"
      :itemSize="171"
      lazy
      class="border border-surface-200 dark:border-surface-700 rounded"
      style="height: calc(100vh - 300px); margin-bottom: -70px"
    >
      <template v-slot:item="{ item }">
        <div class="card-wrapper">
          <TrackCard :data="item" :edit-available="canUpdate" />
        </div>
      </template>
    </VirtualScroller>
  </div>

  <TrackCreator
    :organization-id="route.params.organizationId as string"
    :orbit-id="route.params.id as string"
    :visible="tracksStore.creatorVisible"
    @update:visible="updateCreatorVisible"
  />
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { IconField, InputText, InputIcon, Select, Skeleton, useToast, VirtualScroller } from 'primevue'
import { Library, Plus, Search } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useOrbitsStore } from '@/stores/orbits'
import { useTracksStore } from '@/stores/tracks'
import { useTracksList } from '@/hooks/useTracksList'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { PermissionEnum } from '@/lib/api/api.interfaces'
import TrackCard from '@/components/orbits/tabs/tracks/TrackCard.vue'
import TrackCreator from '@/components/orbits/tabs/tracks/TrackCreator.vue'

const route = useRoute()
const authStore = useAuthStore()
const orbitsStore = useOrbitsStore()
const tracksStore = useTracksStore()
const toast = useToast()

const { setRequestInfo, load, tracksList, isLoading } = useTracksList()

const loading = ref(false)
const searchQuery = ref('')
const typeFilter = ref<string | null>(null)

const TRACK_TYPE_OPTIONS = [
  { label: 'Model', value: 'model' },
  { label: 'Dataset', value: 'dataset' },
  { label: 'Experiment', value: 'experiment' },
]

const canCreate = computed(() => {
  return authStore.isAuth &&
    !!orbitsStore.getCurrentOrbitPermissions?.track?.includes(PermissionEnum.create)
})

const canUpdate = computed(() => {
  return !!orbitsStore.getCurrentOrbitPermissions?.track?.includes(PermissionEnum.update)
})

const filteredTracks = computed(() => {
  let result = tracksList.value
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    result = result.filter((t) => t.name.toLowerCase().includes(q))
  }
  if (typeFilter.value) {
    result = result.filter((t) => t.artifact_type === typeFilter.value)
  }
  return result
})

function updateCreatorVisible(visible: boolean | undefined) {
  visible ? tracksStore.showCreator() : tracksStore.hideCreator()
}

async function loadTracks() {
  const organizationId = route.params.organizationId as string
  const orbitId = route.params.id as string
  if (!organizationId || !orbitId) return

  try {
    loading.value = true
    setRequestInfo({ organizationId, orbitId })
    await load()
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
    await loadTracks()
  },
  { immediate: true },
)

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

.welcome {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-align: center;
  gap: 8px;
  min-height: 150px;
  border-radius: 8px;
  box-shadow: var(--card-shadow);
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  padding: 24px;
}

.welcome__label {
  font-weight: 500;
}

.welcome__text {
  font-size: 12px;
  color: var(--p-text-muted-color);
  margin-bottom: 8px;
}

.toolbar {
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.toolbar :deep(.p-iconfield) {
  max-width: 237px;
}

.toolbar :deep(.p-iconfield .p-inputicon:last-child) {
  inset-inline-end: 9px;
}

.toolbar :deep(.p-iconfield .p-inputtext) {
  width: 100%;
}

.card-wrapper {
  margin-bottom: 24px;
}
</style>
