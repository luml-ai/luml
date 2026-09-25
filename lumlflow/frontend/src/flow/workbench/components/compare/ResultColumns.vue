<template>
  <div class="flex flex-col gap-4">
    <IntegrityWarningBar
      v-for="warning in compare.warnings"
      :key="warning.kind + warning.message"
      :warning="warning"
    />

    <div class="overflow-x-auto">
      <div
        class="grid items-baseline gap-x-6"
        :style="{ gridTemplateColumns: `max-content repeat(${columns.length}, minmax(9rem, 1fr))` }"
      >
        <span />
        <div v-for="column in columns" :key="column.branch" class="flex flex-col gap-1.5 pb-3">
          <div class="flex flex-wrap items-center gap-2">
            <BranchTag :name="column.branch" />
            <!-- Inverted: settled is the ordinary case, so only the deviation
                 is chipped — a badge on almost every column carries no signal. -->
            <span v-if="!column.settled" class="text-sm text-muted-color">working</span>
          </div>
          <!-- The scores below already carry the headline; it is repeated here
               only where there is no table under it to read it from. -->
          <div
            v-if="column.headlineMetric && !scoreNames.length"
            class="flex items-baseline gap-1.5"
          >
            <span class="text-lg font-semibold tabular-nums">
              {{ formatMetric(column.headlineMetric.value) }}
            </span>
            <span class="text-sm text-muted-color">{{ column.headlineMetric.name }}</span>
          </div>
          <!-- Having no numbers and having nothing are different facts: a frame
               reported as never materialized is a wrong answer, not a terse one. -->
          <span
            v-else-if="!column.headlineMetric && !scoreNames.length"
            class="text-base text-muted-color"
          >
            {{
              column.heldKind
                ? `${column.heldKind} · no numbers to compare`
                : 'nothing materialized here'
            }}
          </span>
        </div>

        <template v-for="score in scoreNames" :key="score">
          <span
            class="border-t border-surface-200 py-1.5 pr-2 text-sm text-muted-color dark:border-surface-700"
          >
            {{ score }}
          </span>
          <span
            v-for="column in columns"
            :key="column.branch"
            class="border-t border-surface-200 py-1.5 text-base tabular-nums dark:border-surface-700"
            :class="isBest(score, column) ? 'font-semibold text-(--p-message-success-color)' : ''"
          >
            <template v-if="column.scores[score] !== undefined">
              {{ formatMetric(column.scores[score]) }}
            </template>
            <span v-else class="text-muted-color">—</span>
          </span>
        </template>
      </div>
    </div>

    <!-- Only where the outputs carried curves: an empty chart with axes drawn
         off nothing reads as a run whose metric flatlined. -->
    <div v-if="drawn.length" class="flex flex-col gap-2">
      <p class="font-mono text-sm text-muted-color">{{ compare.sharedMetric }}</p>
      <svg
        :viewBox="`0 0 ${W} ${H}`"
        class="w-full max-w-2xl"
        role="img"
        :aria-label="`${compare.sharedMetric} curves for ${drawn.length} lanes`"
      >
        <line
          v-for="tick in yTicks"
          :key="tick.y"
          :x1="PAD.left"
          :x2="W - PAD.right"
          :y1="tick.y"
          :y2="tick.y"
          stroke="currentColor"
          stroke-width="1"
          class="text-surface-200 dark:text-surface-700"
        />
        <text
          v-for="tick in yTicks"
          :key="'label' + tick.y"
          :x="PAD.left - 6"
          :y="tick.y + 3"
          text-anchor="end"
          font-size="12"
          class="fill-current text-muted-color"
        >
          {{ tick.label }}
        </text>
        <text :x="PAD.left" :y="H - 6" font-size="12" class="fill-current text-muted-color">
          {{ formatMetric(xMin) }}
        </text>
        <text
          :x="W - PAD.right"
          :y="H - 6"
          text-anchor="end"
          font-size="12"
          class="fill-current text-muted-color"
        >
          {{ formatMetric(xMax) }} epochs
        </text>
        <polyline
          v-for="(column, index) in drawn"
          :key="column.branch"
          :points="linePoints(column)"
          fill="none"
          :stroke="branchColor(column.branch)"
          stroke-width="2"
          stroke-linejoin="round"
          stroke-linecap="round"
          :stroke-dasharray="dashFor(index)"
        >
          <title>{{ column.branch }}</title>
        </polyline>
      </svg>
      <div class="flex flex-wrap gap-x-5 gap-y-1.5">
        <span
          v-for="(column, index) in drawn"
          :key="column.branch"
          class="inline-flex items-center gap-1.5 text-sm"
        >
          <svg width="18" height="6" aria-hidden="true">
            <line
              x1="0"
              y1="3"
              x2="18"
              y2="3"
              :stroke="branchColor(column.branch)"
              stroke-width="2"
              :stroke-dasharray="dashFor(index) ? '4 3' : undefined"
            />
          </svg>
          <span class="font-mono">{{ column.branch }}</span>
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { CompareBranchColumn, CompareView } from '../../model/types'
import { formatMetric } from '../../model/format'
import BranchTag from '../../ui/BranchTag.vue'
import { branchColor } from '../../ui/kinds'
import IntegrityWarningBar from './IntegrityWarningBar.vue'

const props = defineProps<{ compare: CompareView }>()

const columns = computed(() => props.compare.branches)

const scoreNames = computed(() => {
  const names: string[] = []
  for (const column of columns.value)
    for (const name of Object.keys(column.scores)) if (!names.includes(name)) names.push(name)
  return names
})

/**
 * Marked only where the comparison declared which way its metric reads. Direction
 * per score is never recorded, so a live comparison declares none and no column
 * is marked best. A green dot on the larger of two losses would be a verdict
 * nobody measured.
 */
const ranked = computed(() => columns.value.some((column) => column.headlineMetric?.higherIsBetter))

const bestByScore = computed<Record<string, number>>(() => {
  const best: Record<string, number> = {}
  for (const name of scoreNames.value) {
    const values = columns.value
      .map((column) => column.scores[name])
      .filter((value): value is number => value !== undefined)
    best[name] = Math.max(...values)
  }
  return best
})

function isBest(score: string, column: CompareBranchColumn): boolean {
  if (!ranked.value) return false
  return column.scores[score] !== undefined && column.scores[score] === bestByScore.value[score]
}

const W = 520
const H = 180
const PAD = { left: 38, right: 12, top: 10, bottom: 22 }

/** The columns whose output carried a curve — the rest have nothing to draw. */
const drawn = computed(() => columns.value.filter((column) => column.curve?.points.length))

const allPoints = computed(() => drawn.value.flatMap((column) => column.curve!.points))
const xMin = computed(() => Math.min(...allPoints.value.map((p) => p[0])))
const xMax = computed(() => Math.max(...allPoints.value.map((p) => p[0])))
const yDomain = computed(() => {
  const ys = allPoints.value.map((p) => p[1])
  const min = Math.min(...ys)
  const max = Math.max(...ys)
  const pad = (max - min) * 0.08 || 0.05
  return { min: min - pad, max: max + pad }
})

function sx(x: number): number {
  return PAD.left + ((x - xMin.value) / (xMax.value - xMin.value || 1)) * (W - PAD.left - PAD.right)
}

function sy(y: number): number {
  const { min, max } = yDomain.value
  return H - PAD.bottom - ((y - min) / (max - min || 1)) * (H - PAD.top - PAD.bottom)
}

function linePoints(column: CompareBranchColumn): string {
  const points = column.curve?.points ?? []
  return points.map(([x, y]) => `${sx(x).toFixed(1)},${sy(y).toFixed(1)}`).join(' ')
}

const yTicks = computed(() => {
  const { min, max } = yDomain.value
  return [min, (min + max) / 2, max].map((value) => ({
    y: sy(value),
    label: formatMetric(value),
  }))
})

// Branches with identical curves would hide each other exactly; dashing the
// later duplicate keeps both visible as "two coincident lines".
function dashFor(index: number): string | undefined {
  const key = JSON.stringify(drawn.value[index].curve?.points)
  for (let j = 0; j < index; j += 1)
    if (JSON.stringify(drawn.value[j].curve?.points) === key) return '6 5'
  return undefined
}
</script>
