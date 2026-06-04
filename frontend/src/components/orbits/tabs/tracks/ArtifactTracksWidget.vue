<template>
  <div class="tracks-section">
    <div class="tracks-section__item">
      <div class="tracks-section__label">Tracks</div>
      <div class="tracks-section__value">
        <span v-if="trackNames.length">{{ trackNames.join(', ') }}</span>
        <span v-else>-</span>
      </div>
    </div>
    <div class="tracks-section__item" style="align-items: center">
      <div class="tracks-section__label"></div>
      <div class="tracks-section__value">
        <Button
          variant="text"
          size="small"
          severity="secondary"
          @click="addToTrackVisible = true"
        >
          Link to track
        </Button>
      </div>
    </div>
  </div>

  <AddToTrackModal
    v-model:visible="addToTrackVisible"
    :artifact-id="artifactId"
    :artifact-type="artifactType"
    :existing-track-ids="existingTrackIds"
    @entry-added="onEntryAdded"
  />
</template>

<script setup lang="ts">
import type { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import { Button, useToast } from 'primevue'
import { computed, onBeforeMount, ref } from 'vue'
import { useTracksStore } from '@/stores/tracks'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import AddToTrackModal from './AddToTrackModal.vue'

type Props = {
  artifactId: string
  artifactType: ArtifactTypeEnum
}

const props = defineProps<Props>()

const tracksStore = useTracksStore()
const toast = useToast()

const addToTrackVisible = ref(false)

const trackNames = computed(() => {
  const names = new Map<string, string>()
  for (const entry of tracksStore.artifactEntries) {
    if (entry.track_id && !names.has(entry.track_id)) {
      names.set(entry.track_id, `Track (v${entry.version})`)
    }
  }
  return Array.from(names.values())
})

const existingTrackIds = computed(() => {
  return new Set(tracksStore.artifactEntries.map((e) => e.track_id))
})

async function loadArtifactEntries() {
  try {
    await tracksStore.listArtifactEntries(props.artifactId)
  } catch {
    toast.add(simpleErrorToast('Failed to load track entries'))
  }
}

async function onEntryAdded() {
  await loadArtifactEntries()
}

onBeforeMount(loadArtifactEntries)
</script>

<style scoped>
.tracks-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.tracks-section__item {
  display: grid;
  align-items: flex-start;
  grid-template-columns: 100px 1fr;
  gap: 24px;
  font-size: 14px;
}
.tracks-section__label {
  color: var(--p-text-muted-color);
  line-height: 1.21;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
