<template>
  <Dialog
    v-model:visible="visible"
    header="Link to Track"
    modal
    :draggable="false"
    :pt="DIALOG_PT"
  >
    <div class="fields">
      <div class="field">
        <label for="track-select" class="label required">Track</label>
        <Select
          v-model="selectedTrackId"
          id="track-select"
          placeholder="Select a track"
          fluid
          option-label="name"
          option-value="id"
          :options="trackOptions"
          :loading="loading"
        >
          <template #option="{ option }">
            <span :class="{ 'option-disabled': option.disabled }">
              {{ option.name }}
              <span v-if="option.disabled" class="option-badge">Already linked</span>
            </span>
          </template>
        </Select>
      </div>
    </div>

    <template #footer>
      <Button
        fluid
        rounded
        :loading="linking"
        :disabled="!selectedTrackId"
        @click="confirmLink"
      >
        Confirm
      </Button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import type { DialogPassThroughOptions } from 'primevue'
import type { ITrackArtifact } from '@/lib/api/orbit-tracks/interfaces'
import { Dialog, Button, Select, useToast } from 'primevue'
import { computed, ref, watch } from 'vue'
import { useTracksStore } from '@/stores/tracks'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { api } from '@/lib/api'
import { useRoute } from 'vue-router'
import type { ITrack } from '@/lib/api/orbit-tracks/interfaces'

type Props = {
  artifactId: string
  artifactType: string
  existingTrackIds: string[]
}

type Emits = {
  (e: 'entryAdded', entry: ITrackArtifact): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()
const visible = defineModel<boolean>('visible')

const DIALOG_PT: DialogPassThroughOptions = {
  root: {
    style: 'max-width: 500px; width: 100%;',
  },
  header: {
    style: 'padding: 28px; text-transform: uppercase; font-size: 20px;',
  },
  content: {
    style: 'padding: 0 28px 28px;',
  },
}

const route = useRoute()
const toast = useToast()
const tracksStore = useTracksStore()

const selectedTrackId = ref<string | null>(null)
const loading = ref(false)
const linking = ref(false)
const allTracks = ref<ITrack[]>([])

const organizationId = computed(() => route.params.organizationId as string)
const orbitId = computed(() => route.params.id as string)

const trackOptions = computed(() => {
  return allTracks.value
    .filter((t) => t.artifact_type === props.artifactType)
    .map((t) => ({
      ...t,
      disabled: props.existingTrackIds.includes(t.id),
    }))
    .filter((t) => !t.disabled)
})

async function loadTracks() {
  try {
    loading.value = true
    const response = await api.orbitTracks.listTracks(organizationId.value, orbitId.value)
    allTracks.value = response.items
  } catch {
    toast.add(simpleErrorToast('Failed to load tracks'))
  } finally {
    loading.value = false
  }
}

async function confirmLink() {
  if (!selectedTrackId.value) return
  try {
    linking.value = true
    const entry = await tracksStore.addEntry(selectedTrackId.value, {
      artifact_id: props.artifactId,
    })
    toast.add(simpleSuccessToast('Artifact linked to track'))
    emit('entryAdded', entry)
    visible.value = false
  } catch (e: any) {
    toast.add(
      simpleErrorToast(e?.response?.data?.detail || e.message || 'Failed to link artifact'),
    )
  } finally {
    linking.value = false
  }
}

watch(visible, (val) => {
  if (val) {
    selectedTrackId.value = null
    allTracks.value = []
    loadTracks()
  }
})
</script>

<style scoped>
.fields {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.label {
  align-self: flex-start;
  font-size: 14px;
}

.option-disabled {
  opacity: 0.5;
}

.option-badge {
  font-size: 11px;
  color: var(--p-text-muted-color);
  font-style: italic;
  margin-left: 8px;
}
</style>
