<template>
  <div class="scatter">
    <div class="legend" data-testid="pca-legend">
      <span class="entry">
        <svg class="swatch" viewBox="0 0 22 12" aria-hidden="true">
          <ellipse class="swatch-ellipse reference" cx="11" cy="6" rx="10" ry="5" />
          <circle class="swatch-dot reference" cx="11" cy="6" r="2" />
        </svg>
        Reference (training)
      </span>
      <span class="entry">
        <svg class="swatch" viewBox="0 0 22 12" aria-hidden="true">
          <ellipse class="swatch-ellipse current" cx="11" cy="6" rx="10" ry="5" />
          <circle class="swatch-dot current" cx="11" cy="6" r="2" />
        </svg>
        Logged (current window)
      </span>
      <span v-if="beyondRange" class="entry muted">
        <svg class="swatch" viewBox="0 0 22 12" aria-hidden="true">
          <circle class="swatch-dot clipped" cx="11" cy="6" r="3" />
        </svg>
        Beyond range
      </span>
    </div>

    <svg :viewBox="`0 0 ${W} ${H}`" class="plot" role="img" aria-label="PC1 × PC2 projection">
      <line
        v-for="tick in yTicks"
        :key="`gy-${tick.value}`"
        class="grid"
        :x1="PAD_L"
        :x2="W - PAD_R"
        :y1="tick.pos"
        :y2="tick.pos"
      />
      <text
        v-for="tick in yTicks"
        :key="`ly-${tick.value}`"
        class="tick"
        :x="PAD_L - 6"
        :y="tick.pos + 3"
        text-anchor="end"
      >
        {{ tick.label }}
      </text>

      <line
        v-for="tick in xTicks"
        :key="`gx-${tick.value}`"
        class="grid"
        :y1="PAD_T"
        :y2="H - PAD_B"
        :x1="tick.pos"
        :x2="tick.pos"
      />
      <text
        v-for="tick in xTicks"
        :key="`lx-${tick.value}`"
        class="tick"
        :x="tick.pos"
        :y="H - PAD_B + 16"
        text-anchor="middle"
      >
        {{ tick.label }}
      </text>

      <!-- the two Gaussians, drawn as their 95% ellipses; this is what the metric compares -->
      <polygon
        v-if="referencePolygon"
        class="ellipse reference"
        :points="referencePolygon"
        data-testid="reference-ellipse"
      />
      <polygon
        v-if="currentPolygon"
        class="ellipse current"
        :points="currentPolygon"
        data-testid="current-ellipse"
      />

      <circle
        v-for="(point, index) in referenceDots"
        :key="`r-${index}`"
        class="dot reference"
        :cx="point.x"
        :cy="point.y"
        r="3"
      />
      <circle
        v-for="(point, index) in currentDots"
        :key="`c-${index}`"
        class="dot current"
        :class="{ clipped: point.clipped }"
        :cx="point.x"
        :cy="point.y"
        r="3"
      />

      <text class="axis-title" :x="(PAD_L + W - PAD_R) / 2" :y="H - 4" text-anchor="middle">
        PC1
      </text>
      <text
        class="axis-title"
        :transform="`rotate(-90 12 ${(PAD_T + H - PAD_B) / 2})`"
        :x="12"
        :y="(PAD_T + H - PAD_B) / 2"
        text-anchor="middle"
      >
        PC2
      </text>
    </svg>

    <p v-if="beyondRange" class="beyond" data-testid="pca-beyond-range">
      {{ beyondRange }} {{ beyondRange === 1 ? 'point' : 'points' }} beyond range, pinned to the
      edge
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { PcaPoint } from '@/api/types'

const W = 640
const H = 260
const PAD_L = 58
const PAD_R = 12
const PAD_T = 12
const PAD_B = 30

// Axes follow the bulk of the data: a handful of extreme rows (a feature sent far out of
// range) would otherwise own the whole width and squash the cloud into a line.
const CLIP_QUANTILE = 0.02
const PAD_SHARE = 0.08

const props = withDefaults(
  defineProps<{
    reference: PcaPoint[]
    current: PcaPoint[]
    referenceEllipse?: PcaPoint[]
    currentEllipse?: PcaPoint[]
  }>(),
  { referenceEllipse: () => [], currentEllipse: () => [] },
)

function quantile(sorted: number[], q: number): number {
  if (!sorted.length) return 0
  const index = Math.min(sorted.length - 1, Math.max(0, Math.round(q * (sorted.length - 1))))
  return sorted[index]
}

/** Range covering the ellipses in full and the point clouds minus their extremes. */
function range(pointValues: number[], ellipseValues: number[]): [number, number] {
  const sorted = [...pointValues].sort((a, b) => a - b)
  let low = sorted.length ? quantile(sorted, CLIP_QUANTILE) : 0
  let high = sorted.length ? quantile(sorted, 1 - CLIP_QUANTILE) : 0
  for (const value of ellipseValues) {
    low = Math.min(low, value)
    high = Math.max(high, value)
  }
  if (high - low < 1e-9) {
    low -= 1
    high += 1
  }
  const pad = (high - low) * PAD_SHARE
  return [low - pad, high + pad]
}

const allPoints = computed(() => [...props.reference, ...props.current])
const allEllipse = computed(() => [...props.referenceEllipse, ...props.currentEllipse])

const xRange = computed(() =>
  range(
    allPoints.value.map((p) => p.x),
    allEllipse.value.map((p) => p.x),
  ),
)
const yRange = computed(() =>
  range(
    allPoints.value.map((p) => p.y),
    allEllipse.value.map((p) => p.y),
  ),
)

function scaleX(value: number): number {
  const [low, high] = xRange.value
  return PAD_L + ((value - low) / (high - low)) * (W - PAD_L - PAD_R)
}

function scaleY(value: number): number {
  const [low, high] = yRange.value
  return H - PAD_B - ((value - low) / (high - low)) * (H - PAD_T - PAD_B)
}

/** Points outside the drawn range are pinned to the edge rather than dropped silently. */
function place(points: PcaPoint[]): { x: number; y: number; clipped: boolean }[] {
  const [xLow, xHigh] = xRange.value
  const [yLow, yHigh] = yRange.value
  return points.map((point) => {
    const clipped = point.x < xLow || point.x > xHigh || point.y < yLow || point.y > yHigh
    return {
      x: scaleX(Math.min(xHigh, Math.max(xLow, point.x))),
      y: scaleY(Math.min(yHigh, Math.max(yLow, point.y))),
      clipped,
    }
  })
}

const referenceDots = computed(() => place(props.reference))
const currentDots = computed(() => place(props.current))
const beyondRange = computed(
  () =>
    referenceDots.value.filter((p) => p.clipped).length +
    currentDots.value.filter((p) => p.clipped).length,
)

function polygon(points: PcaPoint[]): string | null {
  if (points.length < 3) return null
  return points.map((point) => `${scaleX(point.x)},${scaleY(point.y)}`).join(' ')
}

const referencePolygon = computed(() => polygon(props.referenceEllipse))
const currentPolygon = computed(() => polygon(props.currentEllipse))

function ticks(bounds: [number, number], count: number, toPos: (v: number) => number) {
  const [low, high] = bounds
  const step = (high - low) / count
  const magnitude = Math.max(Math.abs(low), Math.abs(high))
  const digits = magnitude >= 100 ? 0 : magnitude >= 10 ? 1 : 2
  return Array.from({ length: count + 1 }, (_, i) => {
    const value = low + step * i
    return { value, pos: toPos(value), label: value.toFixed(digits) }
  })
}

const xTicks = computed(() => ticks(xRange.value, 5, scaleX))
const yTicks = computed(() => ticks(yRange.value, 4, scaleY))
</script>

<style scoped>
.legend {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--luml-space-4);
  margin-bottom: var(--luml-space-2);
}
.entry {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--luml-fg-muted);
}
.entry.muted {
  color: var(--luml-danger);
}
.swatch {
  width: 22px;
  height: 12px;
  flex: 0 0 auto;
}
.swatch-ellipse {
  fill-opacity: 0.1;
  stroke-width: 1.5;
}
.swatch-ellipse.reference {
  fill: var(--luml-fg-muted);
  stroke: var(--luml-fg-muted);
  stroke-dasharray: 4 3;
}
.swatch-ellipse.current {
  fill: var(--luml-warn);
  stroke: var(--luml-warn);
}
.swatch-dot.reference {
  fill: var(--luml-fg-muted);
}
.swatch-dot.current {
  fill: var(--luml-warn);
}
.swatch-dot.clipped {
  fill: none;
  stroke: var(--luml-danger);
  stroke-width: 1.5;
}
.plot {
  width: 100%;
  height: auto;
}
.grid {
  stroke: var(--luml-border);
  stroke-width: 1;
  stroke-dasharray: 4 4;
}
.tick,
.axis-title {
  font-size: 11px;
  fill: var(--luml-fg-muted);
}

.ellipse {
  fill-opacity: 0.1;
  stroke-width: 1.5;
}
.ellipse.reference {
  fill: var(--luml-fg-muted);
  stroke: var(--luml-fg-muted);
  stroke-dasharray: 5 4;
}
/* The logged window is orange against the grey training cloud, as in the design. */
.ellipse.current {
  fill: var(--luml-warn);
  stroke: var(--luml-warn);
}
.dot {
  fill-opacity: 0.65;
}
.dot.reference {
  fill: var(--luml-fg-muted);
}
.dot.current {
  fill: var(--luml-warn);
}
.dot.clipped {
  fill-opacity: 1;
  stroke: var(--luml-danger);
  stroke-width: 1.5;
}
.beyond {
  margin: 6px 0 0;
  font-size: 11px;
  color: var(--luml-fg-muted);
  text-align: right;
}
</style>
