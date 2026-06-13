<template>
  <Dialog
    v-model:visible="visible"
    header="Link a new ARTIFACT"
    modal
    :draggable="false"
    :pt="TRACK_CREATOR_DIALOG_PT"
  >
    <div class="inputs">
      <div class="field">
        <label for="collection" class="label required">Collection</label>
        <Select
          v-model="selectedCollectionId"
          id="collection"
          name="collection"
          placeholder="Select collection"
          fluid
          filter
          :options="collectionsList"
          option-label="name"
          option-value="id"
          :virtualScrollerOptions="collectionScrollerOptions"
          @filter="onCollectionFilter"
        />
      </div>

      <div v-if="selectedCollectionId" class="artifacts-list">
        <div v-if="artifactsLoading" class="artifacts-loading">
          <Skeleton height="60px" />
          <Skeleton height="60px" />
        </div>
        <div v-else-if="artifactsList.length === 0" class="artifacts-empty">
          No matching artifacts found.
        </div>
        <div v-else class="artifacts-grid">
          <div
            v-for="artifact in artifactsList"
            :key="artifact.id"
            class="artifact-card"
            :class="{
              selected: selectedArtifactId === artifact.id,
              disabled: existingArtifactIds.has(artifact.id),
            }"
            @click="selectArtifact(artifact)"
          >
            <div class="artifact-card__header">
              <Tag :value="artifact.type" class="type-tag" />
              <span class="artifact-card__name" v-tooltip="artifact.name">
                {{ artifact.name }}
              </span>
            </div>
            <div class="artifact-card__date">
              {{ new Date(artifact.created_at).toLocaleDateString() }}
            </div>
            <div v-if="artifact.description" class="artifact-card__description">
              {{ artifact.description }}
            </div>
            <div v-if="artifact.tags?.length" class="artifact-card__tags">
              <Tag v-for="tag in artifact.tags" :key="tag" :value="tag" class="small-tag" />
            </div>
            <div v-if="existingArtifactIds.has(artifact.id)" class="artifact-card__badge">
              Already in Track
            </div>
          </div>
        </div>
      </div>
    </div>

    <Button
      type="button"
      fluid
      rounded
      :loading="loading"
      :disabled="!selectedArtifactId"
      @click="onConfirm"
    >
      Confirm
    </Button>
  </Dialog>
</template>

<script setup lang="ts">
import type { Artifact } from '@/lib/api/artifacts/interfaces'
import type { SelectFilterEvent } from 'primevue'
import { Dialog, Button, Select, Tag, Skeleton, useToast } from 'primevue'
import { ref, watch, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useDebounceFn } from '@vueuse/core'
import { useCollectionsList } from '@/hooks/useCollectionsList'
import { useArtifactsList } from '@/hooks/useArtifactsList'
import { useTracksStore } from '@/stores/tracks'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import { TRACK_CREATOR_DIALOG_PT } from './track.const'

type Props = {
  trackId: string
  artifactType: string
  existingArtifactIds: Set<string>
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'entry-added'): void
}>()

const visible = defineModel<boolean>('visible')
const route = useRoute()
const tracksStore = useTracksStore()
const toast = useToast()

const selectedCollectionId = ref<string | null>(null)
const selectedArtifactId = ref<string | null>(null)
const loading = ref(false)
const artifactsLoading = ref(false)

const organizationId = computed(() => String(route.params.organizationId))
const orbitId = computed(() => String(route.params.id))

const {
  setRequestInfo: setCollectionsRequestInfo,
  getInitialPage: getCollectionsInitialPage,
  collectionsList,
  reset: resetCollections,
  onLazyLoad: onCollectionsLazyLoad,
  setSearchQuery: setCollectionsSearch,
} = useCollectionsList(20, false)

const {
  setRequestInfo: setArtifactsRequestInfo,
  getInitialPage: getArtifactsInitialPage,
  list: artifactsList,
  reset: resetArtifacts,
  onLazyLoad: onArtifactsLazyLoad,
  setTypesQuery: setArtifactsTypesQuery,
} = useArtifactsList(50, false)

const collectionScrollerOptions = computed(() => {
  if (collectionsList.value.length < 10) return undefined
  return { lazy: true, onLazyLoad: onCollectionsLazyLoad, itemSize: 38 }
})

const debouncedCollectionFilter = useDebounceFn(async () => {
  try {
    resetCollections()
    setCollectionsRequestInfo({ organizationId: organizationId.value, orbitId: orbitId.value })
    await getCollectionsInitialPage()
  } catch (e) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load collections')))
  }
}, 500)

function onCollectionFilter(event: SelectFilterEvent) {
  setCollectionsSearch(event.value)
  debouncedCollectionFilter()
}

function selectArtifact(artifact: Artifact) {
  if (props.existingArtifactIds.has(artifact.id)) return
  selectedArtifactId.value = artifact.id
}

async function loadArtifacts() {
  if (!selectedCollectionId.value) return
  try {
    artifactsLoading.value = true
    resetArtifacts()
    setArtifactsTypesQuery([props.artifactType as any])
    setArtifactsRequestInfo({
      organizationId: organizationId.value,
      orbitId: orbitId.value,
      collectionId: selectedCollectionId.value,
    })
    await getArtifactsInitialPage()
  } catch (e) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load artifacts')))
  } finally {
    artifactsLoading.value = false
  }
}

async function onConfirm() {
  if (!selectedArtifactId.value) return
  try {
    loading.value = true
    await tracksStore.addEntry(props.trackId, { artifact_id: selectedArtifactId.value })
    toast.add(simpleSuccessToast('Artifact linked to track'))
    visible.value = false
    emit('entry-added')
  } catch (e: any) {
    toast.add(
      simpleErrorToast(e?.response?.data?.detail || getErrorMessage(e, 'Failed to link artifact')),
    )
  } finally {
    loading.value = false
  }
}

watch(selectedCollectionId, () => {
  selectedArtifactId.value = null
  loadArtifacts()
})

watch(visible, async (value) => {
  if (value) {
    selectedCollectionId.value = null
    selectedArtifactId.value = null
    resetCollections()
    resetArtifacts()
    try {
      setCollectionsRequestInfo({ organizationId: organizationId.value, orbitId: orbitId.value })
      await getCollectionsInitialPage()
    } catch (e) {
      toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load collections')))
    }
  }
})
</script>

<style scoped>
.inputs {
  margin-bottom: 28px;
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
.artifacts-list {
  max-height: 360px;
  overflow-y: auto;
}
.artifacts-loading {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.artifacts-empty {
  padding: 16px;
  color: var(--p-text-muted-color);
  text-align: center;
  font-size: 14px;
}
.artifacts-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.artifact-card {
  padding: 12px;
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.15s;
}
.artifact-card:hover:not(.disabled) {
  border-color: var(--p-primary-color);
}
.artifact-card.selected {
  border-color: var(--p-primary-color);
  background-color: var(--p-highlight-background);
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
.artifact-card__name {
  font-weight: 500;
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.artifact-card__date {
  font-size: 12px;
  color: var(--p-text-muted-color);
  margin-bottom: 4px;
}
.artifact-card__description {
  font-size: 13px;
  color: var(--p-text-muted-color);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin-bottom: 4px;
}
.artifact-card__tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.artifact-card__badge {
  font-size: 11px;
  color: var(--p-text-muted-color);
  font-style: italic;
  margin-top: 4px;
}
.type-tag {
  font-weight: 400;
  padding: 2px 6px;
  font-size: 12px;
}
.small-tag {
  font-weight: 400;
  padding: 2px 4px;
  font-size: 11px;
}
</style>
