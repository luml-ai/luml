<template>
  <Button label="Reference profile" severity="secondary" variant="outlined" @click="open" />
  <Dialog
    v-model:visible="visible"
    modal
    block-scroll
    dismissable-mask
    :draggable="false"
    :style="dialogStyle"
    :pt="dialogPt"
  >
    <template #header>
      <div class="header">
        <MEllipsis class="title" :text="feature" />
        <Tag v-if="kind" class="kind" :value="kind" severity="secondary" />
      </div>
    </template>
    <div class="content" :class="{ loading }" :aria-busy="loading">
      <FeatureReferenceLoader v-if="loading && !profile" />
      <MErrorState v-else-if="error" :error="error" @retry="load" />
      <MEmpty v-else-if="emptyState" :title="emptyState.title" :detail="emptyState.detail" />
      <template v-else-if="referenceFeature">
        <FeatureReferenceSummary :stats="stats" />
        <div v-if="probabilities.length" class="probabilities">
          <h4 class="probabilities-title">{{ probabilitiesTitle }}</h4>
          <div class="probability-list">
            <FeatureReferenceProbability
              v-for="item in probabilities"
              :key="item.label"
              :label="item.label"
              :value="item.value"
              :width="item.width"
            />
          </div>
        </div>
        <FeatureReferenceNote
          v-if="note"
          :severity="note.severity"
          :title="note.title"
          :detail="note.detail"
        />
      </template>
    </div>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, ref, shallowRef } from 'vue'
import { Button, Dialog, Tag } from 'primevue'
import { api } from '@/api'
import type { ReferenceProfileResponse } from '@/api/monitoring/interfaces'
import { useFiltersStore } from '@/store/filters'
import type { EmptyStateContent } from '@/types/empty'
import {
  getReferenceNote,
  getReferenceProbabilities,
  getReferenceProbabilitiesTitle,
  getReferenceProfileEmptyState,
  getReferenceStats,
} from '@/utils/reference-profile'
import MEllipsis from '@/components/MEllipsis.vue'
import MEmpty from '@/components/MEmpty.vue'
import MErrorState from '@/components/MErrorState.vue'
import FeatureReferenceLoader from '@/components/feature-drift/FeatureReferenceLoader.vue'
import FeatureReferenceSummary from '@/components/feature-drift/FeatureReferenceSummary.vue'
import FeatureReferenceProbability from '@/components/feature-drift/FeatureReferenceProbability.vue'
import FeatureReferenceNote from '@/components/feature-drift/FeatureReferenceNote.vue'

const DIALOG_GAP = 15

interface Props {
  feature: string
}

const props = defineProps<Props>()

const filtersStore = useFiltersStore()

const visible = ref(false)
const loading = ref(false)
const profile = shallowRef<ReferenceProfileResponse | null>(null)
const error = shallowRef<Error | null>(null)
let requestId = 0

const dialogStyle = {
  width: `calc(100vw - ${2 * DIALOG_GAP}px)`,
  height: `calc(100vh - ${2 * DIALOG_GAP}px)`,
  maxWidth: 'none',
  maxHeight: 'none',
}

const dialogPt = {
  mask: { style: { '--px-mask-background': 'transparent' } },
  header: { class: 'feature-reference-profile-dialog-header' },
  content: { class: 'feature-reference-profile-dialog-content' },
}

const referenceFeature = computed(() => profile.value?.feature ?? null)

const kind = computed(() => referenceFeature.value?.kind.toUpperCase() ?? null)

const stats = computed(() =>
  referenceFeature.value ? getReferenceStats(referenceFeature.value) : [],
)

const probabilities = computed(() =>
  referenceFeature.value ? getReferenceProbabilities(referenceFeature.value) : [],
)

const probabilitiesTitle = computed(() =>
  referenceFeature.value ? getReferenceProbabilitiesTitle(referenceFeature.value) : '',
)

const note = computed(() =>
  profile.value && referenceFeature.value
    ? getReferenceNote(profile.value, referenceFeature.value)
    : null,
)

const emptyState = computed<EmptyStateContent | null>(() => {
  if (!profile.value || referenceFeature.value) return null
  const sectionEmptyState = getReferenceProfileEmptyState(profile.value)
  if (sectionEmptyState) return sectionEmptyState
  return {
    title: 'No reference profile for this feature',
    detail: 'The training baseline does not include this feature.',
  }
})

async function load() {
  const id = ++requestId
  loading.value = true
  try {
    const result = await api.monitoring.getReferenceProfile({
      ...filtersStore.dimensions,
      feature: props.feature,
    })
    if (id !== requestId) return
    profile.value = result
    error.value = null
  } catch (e) {
    if (id !== requestId) return
    error.value = e instanceof Error ? e : new Error(String(e))
  } finally {
    if (id === requestId) loading.value = false
  }
}

function open() {
  visible.value = true
  if (profile.value?.feature?.feature !== props.feature) profile.value = null
  load()
}
</script>

<style scoped>
.header {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.title {
  font-size: 16px;
  font-weight: 500;
  color: var(--p-text-color);
}

.kind {
  flex-shrink: 0;
}

.content {
  display: flex;
  flex-direction: column;
  gap: 16px;
  transition: opacity 0.2s;
}

.content.loading {
  opacity: 0.5;
  pointer-events: none;
}

.probabilities {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.probabilities-title {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
  color: var(--p-text-color);
}

.probability-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
</style>

<style>
.feature-reference-profile-dialog-header {
  border-bottom: 1px solid var(--p-content-border-color);
  padding-top: 9px;
  padding-bottom: 9px;
}

.feature-reference-profile-dialog-content {
  padding-top: 16px;
}
</style>
