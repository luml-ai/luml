<template>
  <section class="reference-profile-tab" data-testid="reference-profile-tab">
    <div class="intro">
      <p class="section-title">Reference profile</p>
      <p class="section-subtitle">
        The training baseline every metric is scored against — the artifact's
        <span class="mono">reference_profile.json</span>, as it ships inside the model.
      </p>
    </div>

    <div class="card">
      <StateBlock
        v-if="view !== 'ready'"
        :view="view"
        :skeleton-rows="4"
        empty-title="No reference profile loaded"
        empty-detail="This deployment's artifact carries no training baseline, so drift and data quality cannot be scored."
      />

      <template v-else-if="document">
        <div class="facts" data-testid="profile-facts">
          <div v-for="fact in facts" :key="fact.label" class="fact">
            <span class="fact-label">{{ fact.label }}</span>
            <span class="fact-value" :class="{ mono: fact.mono }">{{ fact.value }}</span>
          </div>
        </div>

        <div class="toolbar">
          <div class="views" role="tablist">
            <button
              v-for="option in MODES"
              :key="option"
              type="button"
              role="tab"
              class="view"
              :class="{ active: mode === option }"
              :aria-selected="mode === option"
              :data-testid="`profile-view-${option}`"
              @click="mode = option"
            >
              {{ option === 'tree' ? 'Structure' : 'Raw JSON' }}
            </button>
          </div>
          <div class="actions">
            <span class="size">{{ sizeLabel }}</span>
            <button
              type="button"
              class="expand"
              aria-label="Open the profile full screen"
              data-testid="profile-fullscreen-open"
              @click="fullscreen = true"
            >
              <Maximize2 :size="13" />
            </button>
            <CopyButton :value="rawJson" label="reference profile" />
          </div>
        </div>

        <div class="body">
          <JsonNode v-if="mode === 'tree'" :value="document" data-testid="profile-tree" />
          <pre v-else class="mono raw" data-testid="profile-raw">{{ rawJson }}</pre>
        </div>
      </template>
    </div>

    <FieldFullscreen
      v-if="fullscreen"
      name="reference_profile.json"
      :value="rawJson"
      eyebrow="Reference profile"
      @close="fullscreen = false"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Maximize2 } from 'lucide-vue-next'
import type { ReferenceProfileResponse } from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'
import { sectionView } from '@/lib/section'
import StateBlock from '@/components/StateBlock.vue'
import CopyButton from '@/components/CopyButton.vue'
import FieldFullscreen from '@/components/trace/FieldFullscreen.vue'
import JsonNode from './JsonNode.vue'

const MODES = ['tree', 'raw'] as const
type Mode = (typeof MODES)[number]

const props = defineProps<{
  profile: ReferenceProfileResponse | null
  status: LoadStatus
}>()

const view = computed(() => sectionView(props.status, props.profile?.state))
const document = computed(() => props.profile?.document ?? null)

const mode = ref<Mode>('tree')
const fullscreen = ref(false)

const rawJson = computed(() => JSON.stringify(document.value ?? {}, null, 2))

const sizeLabel = computed(() => {
  const lines = rawJson.value.split('\n').length
  return `${lines.toLocaleString()} lines`
})

/** The handful of facts worth reading before the file itself. */
const facts = computed(() => {
  const doc = (document.value ?? {}) as Record<string, unknown>
  const summaries = (doc.feature_summaries ?? {}) as Record<string, Record<string, unknown>>
  const numerical = Object.keys(summaries.numerical_features ?? {}).length
  const categorical = Object.keys(summaries.categorical_features ?? {}).length
  const pca = (doc.pca_profile ?? {}) as Record<string, Record<string, unknown>>
  const components = ((pca.pca?.explained_variance_ratio as number[] | undefined) ?? []).length

  const rows: { label: string; value: string; mono?: boolean }[] = [
    { label: 'Status', value: String(doc.profile_status ?? props.profile?.profile_status ?? '—') },
    { label: 'Task type', value: String(doc.task_type ?? '—') },
    { label: 'Features', value: `${numerical} numerical · ${categorical} categorical` },
  ]
  const samples = doc.n_reference_samples
  if (typeof samples === 'number') {
    rows.push({ label: 'Reference rows', value: samples.toLocaleString() })
  }
  if (components) {
    rows.push({ label: 'PCA components', value: String(components) })
  }
  const output = (doc.output_summary ?? {}) as Record<string, unknown>
  if (output.name) {
    rows.push({ label: 'Monitored output', value: String(output.name), mono: true })
  }
  return rows
})
</script>

<style scoped>
.reference-profile-tab {
  display: flex;
  flex-direction: column;
  gap: var(--luml-space-4);
}
.facts {
  display: flex;
  flex-wrap: wrap;
  gap: var(--luml-space-5);
  padding-bottom: 14px;
  border-bottom: 1px solid var(--luml-border);
}
.fact {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.fact-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--luml-fg-muted);
}
.fact-value {
  font-size: 13.5px;
  font-weight: 500;
  color: var(--luml-fg-strong);
}
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--luml-space-4);
  padding: 12px 0 10px;
}
.views {
  display: flex;
  gap: 4px;
}
.view {
  padding: 4px 10px;
  border: 1px solid var(--luml-border);
  border-radius: var(--luml-radius-md);
  background: var(--luml-bg-card);
  color: var(--luml-fg-muted);
  font: inherit;
  font-size: 12px;
  cursor: pointer;
}
.view.active {
  background: var(--luml-surface-100);
  color: var(--luml-fg-strong);
}
.actions {
  display: flex;
  align-items: center;
  gap: 6px;
}
.size {
  font-size: 11.5px;
  color: var(--luml-fg-muted);
  font-variant-numeric: tabular-nums;
}
.expand {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 3px;
  border: 1px solid transparent;
  border-radius: var(--luml-radius-sm, 4px);
  background: transparent;
  color: var(--luml-fg-muted);
  cursor: pointer;
  line-height: 0;
}
.expand:hover {
  border-color: var(--luml-border);
  background: var(--luml-bg-card);
  color: var(--luml-fg-strong);
}
.body {
  max-height: 560px;
  overflow: auto;
  padding: 12px 14px;
  border: 1px solid var(--luml-surface-100);
  border-radius: var(--luml-radius-md);
  background: var(--luml-surface-100);
}
.raw {
  margin: 0;
  font-size: 12px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--luml-fg);
}
</style>
