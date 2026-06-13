<template>
  <div>
    <UiPageLoader v-if="loading"></UiPageLoader>

    <div v-else-if="tracksStore.currentTrack" class="page-content">
      <Breadcrumb :model="breadcrumbs" :pt="{ root: { style: 'padding-left: 0' } }">
        <template #item="{ item, props: itemProps }">
          <RouterLink
            v-if="item.route"
            v-slot="{ href, navigate }"
            :to="item.route"
            custom
          >
            <a :href="href" v-bind="itemProps.action" @click="navigate">
              {{ item.label }}
            </a>
          </RouterLink>
        </template>
      </Breadcrumb>

      <div class="header">
        <h1 class="header-title">{{ tracksStore.currentTrack.name }}</h1>
        <Button
          v-if="canCreate"
          @click="showAddEntryModal = true"
        >
          <template #icon>
            <Plus :size="14" />
          </template>
          Link artifact
        </Button>
      </div>

      <div class="content">
        <DataTable
          :value="entriesList"
          :pt="TABLE_PT"
          class="table-white"
          scrollable
          scrollHeight="calc(100vh - 340px)"
          :loading="entriesLoading"
          :virtualScrollerOptions="virtualScrollerOptions"
          @row-click="onRowClick"
        >
          <template #empty>
            <div v-if="!isLoading" class="placeholder">
              Link an artifact first.
            </div>
          </template>
          <Column
            field="artifact_name"
            header="Artifact name"
            :pt="{ columnHeaderContent: { style: 'width: 180px' } }"
          >
            <template #body="{ data }: { data: TrackEntry }">
              <div v-tooltip="data.artifact_name" :style="columnBodyStyle + 'width: 180px'">
                {{ data.artifact_name ?? '-' }}
              </div>
            </template>
          </Column>
          <Column
            field="artifact_description"
            header="Description"
            :pt="{ columnHeaderContent: { style: 'width: 203px' } }"
          >
            <template #body="{ data }: { data: TrackEntry }">
              <div
                v-if="data.artifact_description"
                v-tooltip="data.artifact_description"
                class="description"
                style="width: 203px"
              >
                {{ data.artifact_description }}
              </div>
              <div v-else>-</div>
            </template>
          </Column>
          <Column
            field="stage_name"
            header="Stage"
            :pt="{ columnHeaderContent: { style: 'width: 150px' } }"
          >
            <template #body="{ data }: { data: TrackEntry }">
              <Tag
                v-if="data.stage_name"
                :style="getStageBadgeStyle(data.stage_name)"
              >
                {{ data.stage_name }}
              </Tag>
              <span v-else>-</span>
            </template>
          </Column>
          <Column
            field="version"
            header="Version"
            :pt="{ columnHeaderContent: { style: 'width: 100px' } }"
          >
            <template #body="{ data }: { data: TrackEntry }">
              <div :style="columnBodyStyle + 'width: 100px'">
                v{{ data.version }}
              </div>
            </template>
          </Column>
          <Column
            field="created_at"
            header="Creation time"
            :pt="{ columnHeaderContent: { style: 'width: 180px' } }"
          >
            <template #body="{ data }: { data: TrackEntry }">
              <div :style="columnBodyStyle + 'width: 180px'">
                {{ new Date(data.created_at).toLocaleString() }}
              </div>
            </template>
          </Column>
        </DataTable>
      </div>
    </div>

    <Ui404 v-else></Ui404>

    <TrackArtifactPanel
      v-if="selectedEntry"
      :entry="selectedEntry"
      :stages="stages"
      :track-id="tracksStore.currentTrack?.id ?? ''"
      @update:visible="onPanelClose"
      @entry-updated="onEntryUpdated"
      @entry-deleted="onEntryDeleted"
    />

    <TrackAddEntryModal
      v-if="tracksStore.currentTrack"
      v-model:visible="showAddEntryModal"
      :track-id="tracksStore.currentTrack.id"
      :artifact-type="tracksStore.currentTrack.artifact_type"
      :existing-artifact-ids="existingArtifactIds"
      @entry-added="onEntryAdded"
    />
  </div>
</template>

<script setup lang="ts">
import type { MenuItem } from 'primevue/menuitem'
import type { VirtualScrollerProps, DataTableRowClickEvent } from 'primevue'
import type { TrackEntry, TrackStage } from '@/lib/api/orbit-tracks/interfaces'
import { Breadcrumb, Button, DataTable, Column, Tag, useToast } from 'primevue'
import { computed, onBeforeMount, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Plus } from 'lucide-vue-next'
import { useTracksStore } from '@/stores/tracks'
import { useOrbitsStore } from '@/stores/orbits'
import { useTrackEntriesList } from '@/hooks/useTrackEntriesList'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { PermissionEnum } from '@/lib/api/api.interfaces'
import { TABLE_PT, columnBodyStyle } from '@/components/orbits/tabs/registry/collection/artifacts-table/models-table.data'
import { getStageBadgeStyle } from '@/components/orbits/tabs/tracks/stage-colors'
import Ui404 from '@/components/ui/Ui404.vue'
import UiPageLoader from '@/components/ui/UiPageLoader.vue'
import TrackArtifactPanel from '@/components/orbits/tabs/tracks/TrackArtifactPanel.vue'
import TrackAddEntryModal from '@/components/orbits/tabs/tracks/TrackAddEntryModal.vue'

const route = useRoute()
const tracksStore = useTracksStore()
const orbitsStore = useOrbitsStore()
const toast = useToast()

const {
  setRequestInfo,
  getInitialPage,
  entriesList,
  reset: resetEntries,
  isLoading,
  onLazyLoad,
} = useTrackEntriesList()

const loading = ref(true)
const entriesLoading = ref(false)
const showAddEntryModal = ref(false)
const selectedEntry = ref<TrackEntry | null>(null)
const stages = ref<TrackStage[]>([])

const canCreate = computed(() => {
  return !!orbitsStore.getCurrentOrbitPermissions?.track.includes(PermissionEnum.create)
})

const existingArtifactIds = computed(() => {
  return new Set(entriesList.value.map((e) => e.artifact_id))
})

const breadcrumbs = computed<(MenuItem & { route: string })[]>(() => {
  const items: (MenuItem & { route: string })[] = [
    {
      label: 'Registry',
      route: `/organization/${route.params.organizationId}/orbit/${route.params.id}`,
    },
  ]
  if (tracksStore.currentTrack) {
    items.push({
      label: tracksStore.currentTrack.name,
      route: `/organization/${route.params.organizationId}/orbit/${route.params.id}/track/${route.params.trackId}`,
    })
  }
  return items
})

const virtualScrollerOptions = ref<VirtualScrollerProps>({
  lazy: true,
  onLazyLoad: onLazyLoad,
  itemSize: 62,
  scrollHeight: 'calc(100vh - 330px)',
})

function onRowClick(event: DataTableRowClickEvent) {
  const entry = entriesList.value.find((e) => e.id === event.data.id)
  if (entry) {
    selectedEntry.value = entry
  }
}

function onPanelClose() {
  selectedEntry.value = null
}

async function onEntryUpdated() {
  selectedEntry.value = null
  await loadEntries()
}

async function onEntryDeleted() {
  selectedEntry.value = null
  await loadEntries()
}

async function onEntryAdded() {
  await loadEntries()
}

async function loadStages() {
  if (!tracksStore.currentTrack) return
  try {
    stages.value = await tracksStore.listStages(tracksStore.currentTrack.id)
  } catch {
    toast.add(simpleErrorToast('Failed to load stages'))
  }
}

async function loadEntries() {
  if (!tracksStore.currentTrack) return
  try {
    entriesLoading.value = true
    resetEntries()
    setRequestInfo({
      organizationId: String(route.params.organizationId),
      orbitId: String(route.params.id),
      trackId: tracksStore.currentTrack.id,
    })
    await getInitialPage()
  } catch {
    toast.add(simpleErrorToast('Failed to load entries'))
  } finally {
    entriesLoading.value = false
  }
}

async function init() {
  try {
    loading.value = true
    const organizationId = String(route.params.organizationId)
    const orbitId = String(route.params.id)
    const trackId = String(route.params.trackId)

    if (orbitsStore.currentOrbitDetails?.id !== orbitId) {
      const details = await orbitsStore.getOrbitDetails(organizationId, orbitId)
      orbitsStore.setCurrentOrbitDetails(details)
    }

    await tracksStore.setCurrentTrack(trackId)
    await Promise.all([loadStages(), loadEntries()])
  } catch {
    toast.add(simpleErrorToast('Failed to load track data'))
  } finally {
    loading.value = false
  }
}

onBeforeMount(init)

onUnmounted(() => {
  tracksStore.resetCurrentTrack()
})
</script>

<style scoped>
.page-content {
  padding-top: 18px;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.header-title {
  font-weight: 500;
  font-size: 24px;
  line-height: 30px;
  letter-spacing: -0.48px;
}

.content {
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  overflow: hidden;
}

.description {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.placeholder {
  padding: 25px 16px;
  color: var(--p-text-muted-color);
}

:deep(.p-datatable:has(.p-datatable-mask) .p-datatable-tbody) {
  opacity: 0;
}

@media (min-width: 768px) {
  .content {
    margin: 0 -88px;
  }
}
</style>
