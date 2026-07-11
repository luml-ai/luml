<template>
  <DataTable
    v-model:selection="artifactLinksStore.selectedEntries"
    filter-display="menu"
    :value="entriesList"
    :pt="TABLE_PT"
    selection-mode="multiple"
    data-key="id"
    class="table-white"
    scrollable
    scrollHeight="calc(100vh - 340px)"
    :loading="showLoader"
    :virtualScrollerOptions="virtualScrollerOptions"
    @sort="onSort"
  >
    <template #empty>
      <div v-if="!isLoading" class="placeholder">No links to show. Add link to the table.</div>
    </template>
    <Column selectionMode="multiple" :pt="{ headerCell: { style: 'width: 60px' } }"></Column>
    <Column field="id" header="Artifact ID" :pt="{ headerCell: { style: 'width: 180px' } }">
      <template #body="{ data }: { data: TrackEntry }">
        <router-link
          :to="{
            name: 'artifact',
            params: {
              organizationId: route.params.organizationId,
              orbitId: route.params.id,
              collectionId: data.artifact_collection_id,
              artifactId: data.artifact_id,
            },
          }"
          class="id"
        >
          {{ data.id }}
        </router-link>
      </template>
    </Column>
    <Column
      field="artifact_name"
      header="Artifact name"
      sortable
      :pt="{ headerCell: { style: 'width: 200px' } }"
    >
      <template #body="{ data }: { data: TrackEntry }">
        <div class="name">{{ data.artifact_name }}</div>
      </template>
    </Column>
    <Column
      field="description"
      header="Description"
      sortable
      :pt="{ headerCell: { style: 'width: 200px' } }"
    >
      <template #body="{ data }: { data: TrackEntry }">
        <div class="description-wrapper">
          <div v-tooltip.top="data.artifact_description" class="description">
            {{ data.artifact_description }}
          </div>
        </div>
      </template>
    </Column>
    <Column field="stage" header="Stage" sortable :pt="{ headerCell: { style: 'width: 140px' } }">
      <template #body="{ data }: { data: TrackEntry }">
        <div class="stage">
          <Tag
            v-if="data.stage_name"
            :severity="getStageTagSeverity(data.stage_name)"
            class="stage-tag"
          >
            {{ data.stage_name }}
          </Tag>
        </div>
      </template>
    </Column>
    <Column
      field="version"
      header="Version"
      sortable
      :pt="{ headerCell: { style: 'width: 100px' } }"
    >
      <template #body="{ data }: { data: TrackEntry }">
        <div class="version">v{{ data.version }}</div>
      </template>
    </Column>
    <Column
      field="created_at"
      header="Creation time"
      sortable
      :pt="{ headerCell: { style: 'width: 180px' } }"
    >
      <template #body="{ data }: { data: TrackEntry }">
        <div class="creation-time">{{ new Date(data.created_at).toLocaleString() }}</div>
      </template>
    </Column>
  </DataTable>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useTrackEntriesList } from '@/hooks/useTrackEntriesList'
import {
  Column,
  DataTable,
  Tag,
  type VirtualScrollerProps,
  useToast,
  type DataTableSortEvent,
} from 'primevue'
import { useArtifactLinksStore } from '@/stores/artifact-links/artifact-links'
import { getStageTagSeverity, TABLE_PT } from './tracks.const'
import { onBeforeMount } from 'vue'
import { useRoute } from 'vue-router'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import type { GetTrackEntriesListParams, TrackEntry } from '@/lib/api/orbit-tracks/interfaces'

const artifactLinksStore = useArtifactLinksStore()
const route = useRoute()
const toast = useToast()
const { entriesList, isLoading, onLazyLoad, reset, setRequestInfo, getInitialPage, setSortData } =
  useTrackEntriesList(20, true)

const showLoader = computed(() => {
  return isLoading.value && entriesList.value.length === 0
})

const virtualScrollerOptions = computed<VirtualScrollerProps>(() => {
  return {
    lazy: true,
    onLazyLoad: onLazyLoad,
    itemSize: 62,
    scrollHeight: 'calc(100vh - 330px)',
  }
})

const requestInfo = computed(() => {
  return {
    organizationId: String(route.params.organizationId),
    orbitId: String(route.params.id),
    trackId: String(route.params.trackId),
  }
})

function onSort(event: DataTableSortEvent) {
  const sortData = {
    sort_by: event.sortField as GetTrackEntriesListParams['sort_by'],
    order: event.sortOrder === 1 ? 'asc' : ('desc' as GetTrackEntriesListParams['order']),
  }
  setSortData(sortData)
  initList()
}

async function initList() {
  try {
    reset()
    artifactLinksStore.clearSelectedEntries()
    setRequestInfo({
      organizationId: requestInfo.value.organizationId,
      orbitId: requestInfo.value.orbitId,
      trackId: requestInfo.value.trackId,
    })
    await getInitialPage()
  } catch (e) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load artifacts')))
  }
}

onBeforeMount(initList)
</script>

<style scoped>
.placeholder {
  color: var(--p-text-muted-color);
}

.id {
  width: 148px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
  color: var(--p-text-link-color);
  text-decoration: underline;
  display: inline-block;
  transition: color 0.3s;
}

.id:hover {
  color: var(--p-text-link-hover-color);
}

.name {
  width: 170px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.description-wrapper {
  height: 34px;
  display: flex;
  align-items: center;
}

.description {
  width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  line-clamp: 2;
}

.stage {
  width: 110px;
}

.stage-tag {
  max-height: 110px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.version {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.creation-time {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

:deep(.p-datatable-table) {
  table-layout: fixed;
}
</style>
