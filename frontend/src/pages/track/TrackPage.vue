<template>
  <div v-if="loading" class="loading-container">
    <Skeleton style="height: 32px; width: 200px" />
    <Skeleton style="height: 400px" />
  </div>

  <div v-else-if="tracksStore.currentTrack">
    <Breadcrumb :model="breadcrumbs" :pt="{ root: { style: 'padding-left: 0' } }">
      <template #item="{ item, props: itemProps }">
        <RouterLink v-if="item.route" v-slot="{ href, navigate }" :to="item.route" custom>
          <a :href="href" v-bind="itemProps.action" @click="navigate">
            {{ item.label }}
          </a>
        </RouterLink>
      </template>
    </Breadcrumb>

    <div class="page-header">
      <h1 class="page-header__title">{{ tracksStore.currentTrack.name }}</h1>
      <d-button
        v-if="canCreate"
        label="Link artifact"
        @click="addEntryModalVisible = true"
      >
        <template #icon>
          <Plus :size="14" />
        </template>
      </d-button>
    </div>

    <div v-if="entriesList.length === 0" class="empty-state">
      <LinkIcon :size="35" color="var(--p-text-muted-color)" />
      <p class="empty-state__text">Link an artifact first.</p>
    </div>

    <div v-else class="entries-table">
      <DataTable
        :value="entriesList"
        scrollable
        scrollHeight="calc(100vh - 280px)"
        @row-click="onRowClick"
        :pt="{ bodyRow: { style: 'cursor: pointer' } }"
      >
        <Column field="artifact_id" header="Artifact">
          <template #body="{ data }">
            <UiId :id="data.artifact_id" />
          </template>
        </Column>
        <Column field="stage" header="Stage">
          <template #body="{ data }">
            <Tag
              v-if="data.stage"
              :style="getStageBadgeStyle(data.stage.name)"
            >
              {{ data.stage.name }}
            </Tag>
            <span v-else class="no-stage">—</span>
          </template>
        </Column>
        <Column field="version" header="Version">
          <template #body="{ data }">
            v{{ data.version }}
          </template>
        </Column>
        <Column field="created_at" header="Creation time">
          <template #body="{ data }">
            {{ new Date(data.created_at).toLocaleDateString() }}
          </template>
        </Column>
      </DataTable>

      <div v-if="entriesLoading" class="loading-more">
        <ProgressSpinner style="width: 24px; height: 24px" strokeWidth="4" />
      </div>

      <div v-if="hasMoreEntries" class="load-more">
        <Button
          variant="text"
          size="small"
          label="Load more"
          :loading="entriesLoading"
          @click="loadNextPage"
        />
      </div>
    </div>

    <TrackArtifactPanel
      v-model:visible="artifactPanelVisible"
      :entry="selectedEntry"
      :stages="stages"
      :track-id="tracksStore.currentTrack.id"
      @entry-updated="onEntryUpdated"
      @entry-deleted="onEntryDeleted"
    />

    <TrackAddEntryModal
      v-model:visible="addEntryModalVisible"
      :track-artifact-type="tracksStore.currentTrack.artifact_type"
      :existing-entries="entriesList"
      @entry-added="onEntryAdded"
    />
  </div>
</template>

<script setup lang="ts">
import type { ITrackArtifact, ITrackStage } from '@/lib/api/orbit-tracks/interfaces'
import type { MenuItem } from 'primevue/menuitem'
import type { DataTableRowClickEvent } from 'primevue'
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  Breadcrumb,
  Button,
  Column,
  DataTable,
  ProgressSpinner,
  Skeleton,
  Tag,
  useToast,
} from 'primevue'
import { Link as LinkIcon, Plus } from 'lucide-vue-next'
import { useTracksStore } from '@/stores/tracks'
import { useOrbitsStore } from '@/stores/orbits'
import { useTrackEntriesList } from '@/hooks/useTrackEntriesList'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { PermissionEnum } from '@/lib/api/api.interfaces'
import UiId from '@/components/ui/UiId.vue'
import TrackArtifactPanel from '@/components/orbits/tabs/tracks/TrackArtifactPanel.vue'
import TrackAddEntryModal from '@/components/orbits/tabs/tracks/TrackAddEntryModal.vue'

const addEntryModalVisible = ref(false)

const route = useRoute()
const toast = useToast()
const tracksStore = useTracksStore()
const orbitsStore = useOrbitsStore()

const {
  setRequestInfo,
  getInitialPage,
  getNextPage,
  entriesList,
  isLoading: entriesLoading,
  reset: resetEntries,
} = useTrackEntriesList()

const loading = ref(false)
const stages = ref<ITrackStage[]>([])
const artifactPanelVisible = ref(false)
const selectedEntry = ref<ITrackArtifact | null>(null)

const canCreate = computed(() => {
  return !!orbitsStore.getCurrentOrbitPermissions?.track?.includes(PermissionEnum.create)
})

const hasMoreEntries = computed(() => {
  return entriesList.value.length > 0 && entriesList.value.length % 20 === 0
})

const breadcrumbs = computed<(MenuItem & { route: string })[]>(() => {
  const orgId = route.params.organizationId as string
  const orbitId = route.params.id as string
  const list: (MenuItem & { route: string })[] = [
    {
      label: 'Registry',
      route: `/organization/${orgId}/orbit/${orbitId}/tracks`,
    },
  ]
  if (tracksStore.currentTrack) {
    list.push({
      label: tracksStore.currentTrack.name,
      route: `/organization/${orgId}/orbit/${orbitId}/track/${tracksStore.currentTrack.id}`,
    })
  }
  return list
})

function getStageBadgeStyle(stageName: string): Record<string, string> {
  if (stageName === 'Production') {
    return {
      backgroundColor: 'var(--tag-success-background, #DCFCE7)',
      color: 'var(--tag-success-color, #15803D)',
    }
  }
  if (stageName === 'Staging' || stageName === 'Pre-Production') {
    return {
      backgroundColor: 'var(--tag-warn-background, #FFEDD5)',
      color: 'var(--tag-warn-color, #C2410C)',
    }
  }
  return {
    backgroundColor: 'var(--tag-primary-background, #DBEAFE)',
    color: 'var(--tag-primary-color, #1D4ED8)',
  }
}

function onRowClick(event: DataTableRowClickEvent) {
  selectedEntry.value = event.data as ITrackArtifact
  artifactPanelVisible.value = true
}

async function loadNextPage() {
  try {
    await getNextPage()
  } catch {
    toast.add(simpleErrorToast('Failed to load more entries'))
  }
}

function onEntryUpdated(updatedEntry: ITrackArtifact) {
  const index = entriesList.value.findIndex((e) => e.id === updatedEntry.id)
  if (index >= 0) {
    entriesList.value[index] = updatedEntry
  }
}

function onEntryDeleted(entryId: string) {
  const index = entriesList.value.findIndex((e) => e.id === entryId)
  if (index >= 0) {
    entriesList.value.splice(index, 1)
  }
}

function onEntryAdded(entry: ITrackArtifact) {
  entriesList.value.push(entry)
}

async function loadTrackData() {
  const trackId = route.params.trackId as string
  const orgId = route.params.organizationId as string
  const orbitId = route.params.id as string
  if (!trackId || !orgId || !orbitId) return

  try {
    loading.value = true
    await tracksStore.setCurrentTrack(trackId)

    setRequestInfo({ organizationId: orgId, orbitId, trackId })
    await getInitialPage()

    const stagesResponse = await tracksStore.listStages(trackId)
    stages.value = stagesResponse.items
  } catch {
    toast.add(simpleErrorToast('Failed to load track'))
  } finally {
    loading.value = false
  }
}

watch(
  () => route.params.trackId,
  async (newId) => {
    if (!newId) return
    resetEntries()
    await loadTrackData()
  },
  { immediate: true },
)

onUnmounted(() => {
  tracksStore.resetCurrentTrack()
  resetEntries()
})
</script>

<style scoped>
.loading-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding-top: 20px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.page-header__title {
  font-weight: 500;
  font-size: 20px;
  line-height: 30px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-align: center;
  gap: 8px;
  min-height: 200px;
  border-radius: 8px;
  box-shadow: var(--card-shadow);
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  padding: 24px;
}

.empty-state__text {
  color: var(--p-text-muted-color);
  font-size: 14px;
}

.entries-table {
  border-radius: 8px;
  overflow: hidden;
}

.no-stage {
  color: var(--p-text-muted-color);
}

.loading-more {
  display: flex;
  justify-content: center;
  padding: 12px;
}

.load-more {
  display: flex;
  justify-content: center;
  padding: 8px;
}
</style>
