<template>
  <section class="data-quality" data-testid="data-quality-tab">
    <div class="intro">
      <p class="section-title">Data quality</p>
      <p class="section-subtitle">
        Are incoming features well-formed, or did an upstream pipeline break?
      </p>
    </div>

    <StaleWindowNotice
      v-if="dataQuality?.stale"
      :computed-at="dataQuality.computed_at"
      :window="window"
    />

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

      <!-- Same viewport as the Traces table: past that the list scrolls, not the page. -->
      <div v-else-if="dataQuality" class="table-scroll table-viewport">
        <table class="dq" data-testid="data-quality-table">
          <thead>
            <tr>
              <th>
                <button type="button" class="sort" data-testid="dq-sort-feature" @click="toggleSort('feature')">
                  Feature <span class="arrow">{{ arrow('feature') }}</span>
                </button>
              </th>
              <th class="num">
                <button type="button" class="sort" data-testid="dq-sort-missing" @click="toggleSort('missing')">
                  Missing <span class="arrow">{{ arrow('missing') }}</span>
                </button>
              </th>
              <th class="num">
                <button type="button" class="sort" data-testid="dq-sort-type" @click="toggleSort('type')">
                  Type errors <span class="arrow">{{ arrow('type') }}</span>
                </button>
              </th>
              <th>
                <button type="button" class="sort" data-testid="dq-sort-range" @click="toggleSort('range')">
                  Range / unseen <span class="arrow">{{ arrow('range') }}</span>
                </button>
              </th>
              <th>
                <button type="button" class="sort" data-testid="dq-sort-status" @click="toggleSort('status')">
                  Status <span class="arrow">{{ arrow('status') }}</span>
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in sortedFeatures"
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
                <span v-if="row.missing_delta != null" class="rate-delta" :class="deltaTone(row.missing_delta)">
                  {{ deltaLabel(row.missing_delta) }}
                </span>
              </td>
              <td class="mono num" :class="rateClass(row.type_error_rate, 'type_mismatch')">
                {{ formatRate(row.type_error_rate) }}
                <span v-if="row.type_error_delta != null" class="rate-delta" :class="deltaTone(row.type_error_delta)">
                  {{ deltaLabel(row.type_error_delta) }}
                </span>
              </td>
              <td class="mono range">
                {{ rangeLabel(row) }}
                <span v-if="row.range_unseen_delta != null" class="rate-delta" :class="deltaTone(row.range_unseen_delta)">
                  {{ deltaLabel(row.range_unseen_delta) }}
                </span>
              </td>
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
import { Window } from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'
import { sectionView } from '@/lib/section'
import { formatRate } from '@/lib/format'
// the cells explain the status tag next to them, so both read the same thresholds
import { rateClass } from '@/lib/dataQuality'
import StateBlock from '@/components/StateBlock.vue'
import SeverityTag from '@/components/SeverityTag.vue'
import AlertBannerList from '@/components/overview/AlertBannerList.vue'
import DetailDrawer from '@/components/DetailDrawer.vue'
import StaleWindowNotice from '@/components/StaleWindowNotice.vue'
import InvalidValuesPanel from './InvalidValuesPanel.vue'

const props = withDefaults(
  defineProps<{
    dataQuality: DataQualityResponse | null
    status: LoadStatus
    /** The selected range, so a snapshot from outside it can name what it fell out of. */
    window?: Window
    trends?: Series[]
    trendsStatus?: LoadStatus
    /** A feature an alert asked to open; its panel opens as soon as the rows arrive. */
    focusFeature?: string | null
  }>(),
  { trends: () => [], trendsStatus: 'idle', focusFeature: null, window: Window.H24 },
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

// Only one of the two checks applies; the column names the one that ran.
function rangeLabel(row: DataQualityFeatureRow): string {
  if (row.range_violation_rate != null) return `${formatRate(row.range_violation_rate)} out of range`
  if (row.unseen_category_rate != null) return `${formatRate(row.unseen_category_rate)} unseen`
  return formatRate(row.range_unseen_rate)
}

/** A quality rate growing is bad news; the delta chip's color follows the meaning. */
function deltaTone(delta: number): string {
  return delta > 0 ? 'up' : 'down'
}

function deltaLabel(delta: number): string {
  const points = Math.abs(delta * 100)
  const text = points >= 10 ? points.toFixed(0) : points.toFixed(1)
  return `${delta > 0 ? '↑' : '↓'} ${text}pp`
}

type DqSortKey = 'feature' | 'missing' | 'type' | 'range' | 'status'
const SEVERITY_RANK: Record<string, number> = { ok: 0, warning: 1, critical: 2 }

const sortKey = ref<DqSortKey | null>(null)
const sortDesc = ref(true)

function toggleSort(key: DqSortKey): void {
  if (sortKey.value === key) {
    sortDesc.value = !sortDesc.value
  } else {
    sortKey.value = key
    // rates and status start with the worst on top; names start alphabetical
    sortDesc.value = key !== 'feature'
  }
}

function arrow(key: DqSortKey): string {
  if (sortKey.value !== key) return '↕'
  return sortDesc.value ? '↓' : '↑'
}

const sortedFeatures = computed(() => {
  const rows = props.dataQuality?.features ?? []
  const key = sortKey.value
  if (key === null) return rows
  const value = (row: DataQualityFeatureRow): number | string => {
    if (key === 'feature') return row.feature
    if (key === 'missing') return row.missing_rate ?? -1
    if (key === 'type') return row.type_error_rate ?? -1
    if (key === 'range') return row.range_unseen_rate ?? -1
    return SEVERITY_RANK[row.status] ?? 0
  }
  const sorted = [...rows].sort((a, b) => {
    const va = value(a)
    const vb = value(b)
    return typeof va === 'string' ? String(va).localeCompare(String(vb)) : Number(va) - Number(vb)
  })
  return sortDesc.value ? sorted.reverse() : sorted
})

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
.sort {
  border: none;
  background: transparent;
  padding: 0;
  font: inherit;
  color: inherit;
  cursor: pointer;
  white-space: nowrap;
}
.sort:hover {
  color: var(--luml-fg-strong);
}
.arrow {
  font-size: 10px;
  opacity: 0.7;
}
.dq th {
  text-align: left;
  padding: 8px 12px;
  color: var(--luml-fg-muted);
  font-weight: 500;
  border-bottom: 1px solid var(--luml-border);
  white-space: nowrap;
  /* the header stays put while the list scrolls under it */
  position: sticky;
  top: 0;
  z-index: 1;
  background: var(--luml-bg-card);
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
.rate-delta {
  display: block;
  font-size: 10.5px;
  font-variant-numeric: tabular-nums;
}
.rate-delta.up {
  color: var(--luml-danger-tint-fg);
}
.rate-delta.down {
  color: var(--luml-success-tint-fg);
}
.feature {
  font-weight: 500;
  color: var(--luml-fg-strong);
}
</style>
