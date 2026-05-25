<template>
  <div class="tracks-widget">
    <div class="tracks-widget__header">
      <span class="tracks-widget__label">Tracks</span>
    </div>
    <div class="tracks-widget__content">
      <span v-if="trackNames.length" class="tracks-widget__names">
        {{ trackNames.join(', ') }}
      </span>
      <Button
        variant="text"
        size="small"
        severity="secondary"
        @click="addToTrackVisible = true"
      >
        Link to track
      </Button>
    </div>

    <AddToTrackModal
      v-model:visible="addToTrackVisible"
      :artifact-id="artifactId"
      :artifact-type="artifactType"
      :existing-track-ids="existingTrackIds"
      @entry-added="onEntryAdded"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Button, useToast } from 'primevue'
import { useTracksStore } from '@/stores/tracks'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import type { ITrack, ITrackArtifact } from '@/lib/api/orbit-tracks/interfaces'
import { api } from '@/lib/api'
import { useRoute } from 'vue-router'
import AddToTrackModal from './AddToTrackModal.vue'

type Props = {
  artifactId: string
  artifactType: string
}

const props = defineProps<Props>()

const route = useRoute()
const toast = useToast()
const tracksStore = useTracksStore()

const addToTrackVisible = ref(false)
const allTracks = ref<ITrack[]>([])

const trackNames = computed(() => {
  return tracksStore.artifactEntries
    .map((entry) => {
      const track = allTracks.value.find((t) => t.id === entry.track_id)
      return track?.name
    })
    .filter(Boolean) as string[]
})

const existingTrackIds = computed(() => {
  return tracksStore.artifactEntries.map((entry) => entry.track_id)
})

function onEntryAdded(_entry: ITrackArtifact) {
  loadData()
}

async function loadData() {
  const orgId = route.params.organizationId as string
  const orbitId = route.params.id as string
  try {
    const [tracksResponse] = await Promise.all([
      api.orbitTracks.listTracks(orgId, orbitId),
      tracksStore.loadArtifactEntries(props.artifactId),
    ])
    allTracks.value = tracksResponse.items
  } catch {
    toast.add(simpleErrorToast('Failed to load track entries'))
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.tracks-widget {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tracks-widget__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.tracks-widget__label {
  font-size: 14px;
  color: var(--p-text-muted-color);
}

.tracks-widget__content {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.tracks-widget__names {
  font-size: 14px;
}
</style>
