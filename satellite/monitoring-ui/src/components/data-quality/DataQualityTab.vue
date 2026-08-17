<template>
  <section class="data-quality" data-testid="data-quality-tab">
    <div class="intro">
      <p class="section-title">Data quality</p>
      <p class="section-subtitle">
        Are incoming features well-formed, or did an upstream pipeline break?
      </p>
    </div>

    <AlertBannerList
      v-if="dataQuality?.alerts?.length"
      :banners="dataQuality.alerts"
      inspectable
      @show-feature="$emit('show-feature', $event)"
      @acknowledge="$emit('acknowledge', $event)"
    />

    <div class="card">
      <StateBlock
        v-if="view !== 'ready'"
        :view="view"
        :skeleton-rows="4"
        empty-title="No data quality results yet"
        empty-detail="The worker has not materialized data quality for this window yet."
      />

      <div v-else-if="dataQuality" class="table-scroll">
        <table class="dq" data-testid="data-quality-table">
          <thead>
            <tr>
              <th>Feature</th>
              <th class="num">Missing</th>
              <th class="num">Type errors</th>
              <th>Range / unseen</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in dataQuality.features"
              :key="row.feature"
              class="row"
              :class="{ selected: row.feature === selected?.feature }"
              data-testid="dq-row"
              role="button"
              tabindex="0"
              :aria-label="`Inspect ${row.feature}`"
              @click="inspect(row)"
              @keydown.enter.prevent="inspect(row)"
              @keydown.space.prevent="inspect(row)"
            >
              <td class="mono feature" :title="checkedTitle(row)">{{ row.feature }}</td>
              <td class="mono num" :class="rateClass(row.missing_rate, 'missing')">
                {{ formatRate(row.missing_rate) }}
              </td>
              <td class="mono num" :class="rateClass(row.type_error_rate, 'type_mismatch')">
                {{ formatRate(row.type_error_rate) }}
              </td>
              <td class="mono range">{{ rangeLabel(row) }}</td>
              <td><SeverityTag :severity="row.status" /></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- what the rates counted, one click away from the row that reports them -->
    <DetailDrawer
      :open="selected !== null"
      :feature="selected?.feature ?? null"
      :kind="kindLabel"
      :caption="drawerCaption"
      eyebrow="Input quality"
      testid="invalid-values-drawer"
      @close="inspect(null)"
    >
      <template #status>
        <SeverityTag v-if="selected" :severity="selected.status" />
      </template>
      <InvalidValuesPanel
        v-if="selected"
        :row="selected"
        :trends="trends"
        :trends-status="trendsStatus"
      />
    </DetailDrawer>

  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type {
  AlertBanner,
  DataQualityFeatureRow,
  DataQualityResponse,
  Series,
} from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'
import { sectionView } from '@/lib/section'
import { formatRate } from '@/lib/format'
// the cells explain the status tag next to them, so both read the same thresholds
import { rateClass } from '@/lib/dataQuality'
import StateBlock from '@/components/StateBlock.vue'
import SeverityTag from '@/components/SeverityTag.vue'
import AlertBannerList from '@/components/overview/AlertBannerList.vue'
import DetailDrawer from '@/components/DetailDrawer.vue'
import InvalidValuesPanel from './InvalidValuesPanel.vue'

const props = withDefaults(
  defineProps<{
    dataQuality: DataQualityResponse | null
    status: LoadStatus
    trends?: Series[]
    trendsStatus?: LoadStatus
    /** A feature an alert asked to open; its panel opens as soon as the rows arrive. */
    focusFeature?: string | null
  }>(),
  { trends: () => [], trendsStatus: 'idle', focusFeature: null },
)

// The history behind a feature's rates is fetched only when its panel opens.
const emit = defineEmits<{
  inspect: [string | null]
  'show-feature': [AlertBanner]
  acknowledge: [AlertBanner]
}>()

const view = computed(() => sectionView(props.status, props.dataQuality?.state))

const selected = ref<DataQualityFeatureRow | null>(null)

function inspect(row: DataQualityFeatureRow | null): void {
  selected.value = row
  emit('inspect', row?.feature ?? null)
}

const kindLabel = computed(() => {
  if (!selected.value?.kind) return null
  return selected.value.kind === 'categorical' ? 'Categorical' : 'Numerical'
})

const drawerCaption = computed(() => {
  const checked = selected.value?.checked
  return checked == null
    ? 'Live values checked against the training reference'
    : `${checked.toLocaleString()} values checked against the training reference`
})

watch(
  [() => props.focusFeature, () => props.dataQuality],
  ([feature, response]) => {
    if (!feature || selected.value?.feature === feature) return
    const row = response?.features.find((entry) => entry.feature === feature)
    if (row) inspect(row)
  },
  { immediate: true },
)

// A panel describing one window's row must not outlive the row itself.
watch(
  () => props.dataQuality,
  (response) => {
    if (!selected.value) return
    const name = selected.value.feature
    const stillThere = response?.features.find((row) => row.feature === name) ?? null
    selected.value = stillThere
    if (stillThere === null) emit('inspect', null)
  },
)

// A feature is either numerical or categorical, so only one of the two checks applies —
// the column names the one that ran instead of showing a bare number.
function rangeLabel(row: DataQualityFeatureRow): string {
  if (row.range_violation_rate != null) return `${formatRate(row.range_violation_rate)} out of range`
  if (row.unseen_category_rate != null) return `${formatRate(row.unseen_category_rate)} unseen`
  return formatRate(row.range_unseen_rate)
}

function checkedTitle(row: DataQualityFeatureRow): string | undefined {
  return row.checked == null ? undefined : `${row.checked.toLocaleString()} values checked`
}
</script>

<style scoped>
.data-quality {
  display: flex;
  flex-direction: column;
  gap: var(--luml-space-4);
}
.table-scroll {
  overflow-x: auto;
}
.dq {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.dq th {
  text-align: left;
  padding: 12px 18px;
  background: var(--luml-surface-50);
  color: var(--luml-fg-muted);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  border-bottom: 1px solid var(--luml-border);
  white-space: nowrap;
}
.row {
  cursor: pointer;
}
.row:hover td,
.row.selected td {
  background: var(--luml-surface-50);
}
.dq td {
  padding: 13px 18px;
  border-bottom: 1px solid var(--luml-surface-100);
  color: var(--luml-fg);
}
.dq tbody tr:last-child td {
  border-bottom: none;
}
.dq td.range {
  color: var(--luml-fg-muted);
  white-space: nowrap;
}
.dq td.warn {
  color: var(--luml-warn-tint-fg);
}
.dq td.critical {
  color: var(--luml-danger-tint-fg);
}
.dq .num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.feature {
  font-weight: 500;
  color: var(--luml-fg-strong);
}
</style>
