<template>
  <div class="card" @click="goToTrack">
    <div class="left">
      <div class="label">{{ data.name }}</div>
      <div class="info">
        <div class="info-item">
          <History :size="12" />
          <span>{{ updatedText }}</span>
        </div>
        <div class="info-item">
          <component
            v-if="TRACK_TYPE_CONFIG[data.artifact_type]"
            :is="TRACK_TYPE_CONFIG[data.artifact_type].icon"
            :size="12"
          />
          <span>{{ TRACK_TYPE_CONFIG[data.artifact_type]?.label ?? 'Unknown type' }}</span>
        </div>
        <div class="info-item">
          <Database :size="12" />
          <span>{{ data.total_entries }}</span>
        </div>
      </div>
      <div class="id-row">
        <span class="id-text">Id: </span>
        <UiId :id="data.id" class="id-value" />
      </div>
    </div>
    <div v-if="editAvailable" class="right">
      <Button severity="secondary" variant="text" @click.stop="isSettingsVisible = true">
        <template #icon>
          <Settings :size="14" />
        </template>
      </Button>
    </div>
  </div>

  <TrackSettingsPanel
    v-model:visible="isSettingsVisible"
    :data="currentData"
    :stages="stages"
    :stages-in-use="stagesInUse"
    @track-updated="onTrackUpdated"
    @track-deleted="onTrackDeleted"
    @stages-changed="loadStages"
  />
</template>

<script setup lang="ts">
import type { ITrack, ITrackStage } from '@/lib/api/orbit-tracks/interfaces'
import { Button, useToast } from 'primevue'
import { History, Database, Settings, CircuitBoard, FileChartColumn, FlaskConical } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { getLastUpdateText } from '@/helpers/helpers'
import { api } from '@/lib/api'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { useTracksStore } from '@/stores/tracks'
import UiId from '@/components/ui/UiId.vue'
import TrackSettingsPanel from './TrackSettingsPanel.vue'

type Props = {
  data: ITrack
  editAvailable: boolean
}

const props = defineProps<Props>()

const router = useRouter()
const toast = useToast()
const tracksStore = useTracksStore()

const isSettingsVisible = ref(false)
const currentData = ref<ITrack>(props.data)
const stages = ref<ITrackStage[]>([])
const stagesInUse = ref<Set<string>>(new Set())

const TRACK_TYPE_CONFIG: Record<string, { label: string; icon: typeof CircuitBoard }> = {
  model: { label: 'Model', icon: CircuitBoard },
  dataset: { label: 'Dataset', icon: FileChartColumn },
  experiment: { label: 'Experiment', icon: FlaskConical },
}

const updatedText = computed(() => {
  return getLastUpdateText(currentData.value.updated_at || currentData.value.created_at)
})

async function loadStages() {
  try {
    const response = await tracksStore.listStages(props.data.id)
    stages.value = response.items

    const inUseIds = new Set<string>()
    try {
      const entries = await api.orbitTracks.listEntries(
        tracksStore.requestInfo.organizationId,
        tracksStore.requestInfo.orbitId,
        props.data.id,
        { page_size: 100 },
      )
      for (const entry of entries.items) {
        if (entry.stage?.id) {
          inUseIds.add(entry.stage.id)
        }
      }
    } catch {
      // If we can't load entries, assume no stages are in use
    }
    stagesInUse.value = inUseIds
  } catch {
    toast.add(simpleErrorToast('Failed to load stages'))
  }
}

watch(isSettingsVisible, (val) => {
  if (val) {
    loadStages()
  }
})

function onTrackUpdated(track: ITrack) {
  currentData.value = track
}

function onTrackDeleted() {
  router.push({
    name: 'orbit-tracks',
    params: {
      id: props.data.orbit_id,
    },
  })
}

function goToTrack() {
  router.push({
    name: 'track',
    params: {
      id: props.data.orbit_id,
      trackId: props.data.id,
    },
  })
}
</script>

<style scoped>
.card {
  display: flex;
  gap: 24px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  box-shadow: var(--card-shadow);
  padding: 16px 16px 6px;
  border-radius: 8px;
  justify-content: space-between;
  cursor: pointer;
  transition: background-color 0.3s;
  height: 147px;
  width: calc(100vw - 379px);
}
.card:hover {
  background-color: var(--p-autocomplete-chip-focus-background);
}
.left {
  width: calc(100% - 60px);
}
.label {
  font-weight: 500;
  margin-bottom: 8px;
}
.info {
  display: flex;
  gap: 12px;
  margin-bottom: 8px;
}
.info-item {
  display: flex;
  align-items: center;
  font-size: 12px;
  gap: 4px;
  color: var(--p-text-muted-color);
}
.id-row {
  font-size: 12px;
  margin-bottom: 20px;
}
.id-text {
  color: var(--p-text-muted-color);
}
.right {
  flex: 0 0 auto;
  align-self: center;
  padding-bottom: 10px;
}

@media (max-width: 768px) {
  .card {
    width: calc(100vw - 30px);
  }
}
</style>
