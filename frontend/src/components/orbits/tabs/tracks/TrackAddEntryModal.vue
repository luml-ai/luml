<template>
  <Dialog
    v-model:visible="visible"
    header="Link a new ARTIFACT"
    modal
    :draggable="false"
    :pt="DIALOG_PT"
  >
    <div class="fields">
      <div class="field">
        <label for="collection" class="label required">Collection</label>
        <Select
          v-model="selectedCollectionId"
          id="collection"
          placeholder="Select collection"
          fluid
          option-label="name"
          option-value="id"
          :options="filteredCollections"
          :loading="collectionsLoading"
        />
      </div>

      <div v-if="selectedCollectionId" class="artifacts-section">
        <div v-if="artifactsLoading" class="artifacts-loading">
          <Skeleton style="height: 60px" />
          <Skeleton style="height: 60px" />
        </div>

        <div v-else-if="artifactsList.length === 0" class="artifacts-empty">
          No matching artifacts found.
        </div>

        <div v-else class="artifacts-list">
          <div
            v-for="artifact in artifactsList"
            :key="artifact.id"
            class="artifact-card"
            :class="{
              selected: selectedArtifactId === artifact.id,
              disabled: isAlreadyInTrack(artifact.id),
            }"
            @click="selectArtifact(artifact)"
          >
            <div class="artifact-card__header">
              <Tag :value="artifact.type" class="artifact-card__type" />
              <span class="artifact-card__name">{{ artifact.name }}</span>
            </div>
            <div class="artifact-card__meta">
              <span>{{ new Date(artifact.created_at).toLocaleDateString() }}</span>
              <span v-if="artifact.description" class="artifact-card__desc">
                {{ artifact.description }}
              </span>
            </div>
            <div v-if="artifact.tags?.length" class="artifact-card__tags">
              <Tag v-for="tag in artifact.tags" :key="tag" :value="tag" severity="secondary" />
            </div>
            <div v-if="isAlreadyInTrack(artifact.id)" class="artifact-card__badge">
              Already in Track
            </div>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <Button
        fluid
        rounded
        :loading="linking"
        :disabled="!selectedArtifactId"
        @click="confirmLink"
      >
        Confirm
      </Button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import type { DialogPassThroughOptions } from 'primevue'
import type { Artifact } from '@/lib/api/artifacts/interfaces'
import type { OrbitCollection } from '@/lib/api/orbit-collections/interfaces'
import { Dialog, Button, Select, Skeleton, Tag, useToast } from 'primevue'
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '@/lib/api'
import { useTracksStore } from '@/stores/tracks'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import type { ITrackArtifact } from '@/lib/api/orbit-tracks/interfaces'

type Props = {
  trackArtifactType: string
  existingEntries: ITrackArtifact[]
}

type Emits = {
  (e: 'entryAdded', entry: ITrackArtifact): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()
const visible = defineModel<boolean>('visible')

const DIALOG_PT: DialogPassThroughOptions = {
  root: {
    style: 'max-width: 600px; width: 100%;',
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

const selectedCollectionId = ref<string | null>(null)
const selectedArtifactId = ref<string | null>(null)
const collectionsLoading = ref(false)
const artifactsLoading = ref(false)
const linking = ref(false)
const collectionsList = ref<OrbitCollection[]>([])
const artifactsList = ref<Artifact[]>([])

const organizationId = computed(() => route.params.organizationId as string)
const orbitId = computed(() => route.params.id as string)

const filteredCollections = computed(() => {
  return collectionsList.value.filter((c) => {
    return c.type === props.trackArtifactType || c.type === 'mixed'
  })
})

function isAlreadyInTrack(artifactId: string): boolean {
  return props.existingEntries.some((entry) => entry.artifact_id === artifactId)
}

function selectArtifact(artifact: Artifact) {
  if (isAlreadyInTrack(artifact.id)) return
  selectedArtifactId.value = artifact.id
}

async function loadCollections() {
  try {
    collectionsLoading.value = true
    const response = await api.orbitCollections.getCollectionsList(
      organizationId.value,
      orbitId.value,
      { cursor: null, limit: 100 },
    )
    collectionsList.value = response.items
  } catch {
    toast.add(simpleErrorToast('Failed to load collections'))
  } finally {
    collectionsLoading.value = false
  }
}

async function loadArtifacts(collectionId: string) {
  try {
    artifactsLoading.value = true
    const controller = new AbortController()
    const response = await api.artifacts.getList(
      organizationId.value,
      orbitId.value,
      collectionId,
      { cursor: null, limit: 100, types: [props.trackArtifactType as any] },
      controller.signal,
    )
    artifactsList.value = response.items
  } catch {
    toast.add(simpleErrorToast('Failed to load artifacts'))
  } finally {
    artifactsLoading.value = false
  }
}

async function confirmLink() {
  if (!selectedArtifactId.value) return
  const trackId = route.params.trackId as string
  try {
    linking.value = true
    const entry = await tracksStore.addEntry(trackId, { artifact_id: selectedArtifactId.value })
    toast.add(simpleSuccessToast('Artifact linked'))
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

watch(selectedCollectionId, async (id) => {
  selectedArtifactId.value = null
  artifactsList.value = []
  if (id) {
    await loadArtifacts(id)
  }
})

watch(visible, (val) => {
  if (val) {
    selectedCollectionId.value = null
    selectedArtifactId.value = null
    artifactsList.value = []
    collectionsList.value = []
    loadCollections()
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

.artifacts-section {
  max-height: 400px;
  overflow-y: auto;
}

.artifacts-loading {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.artifacts-empty {
  color: var(--p-text-muted-color);
  font-size: 14px;
  text-align: center;
  padding: 24px;
}

.artifacts-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.artifact-card {
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  transition: border-color 0.15s;
}

.artifact-card:hover:not(.disabled) {
  border-color: var(--p-primary-color);
}

.artifact-card.selected {
  border-color: var(--p-primary-color);
  background-color: var(--p-primary-50, rgba(59, 130, 246, 0.05));
}

.artifact-card.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.artifact-card__header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.artifact-card__type {
  font-weight: 400;
  padding: 2px 6px;
  font-size: 12px;
}

.artifact-card__name {
  font-weight: 500;
  font-size: 14px;
}

.artifact-card__meta {
  font-size: 12px;
  color: var(--p-text-muted-color);
  display: flex;
  gap: 12px;
}

.artifact-card__desc {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 300px;
}

.artifact-card__tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
  margin-top: 6px;
}

.artifact-card__badge {
  margin-top: 6px;
  font-size: 11px;
  color: var(--p-text-muted-color);
  font-style: italic;
}
</style>
