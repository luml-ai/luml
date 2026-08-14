<template>
  <div class="min-w-0 flex flex-col gap-1">
    <div class="flex items-baseline justify-between gap-3 text-xs">
      <span class="text-muted-color truncate">{{ name }}</span>
      <span class="font-medium tabular-nums whitespace-nowrap">{{ readout }}</span>
    </div>
    <svg
      :viewBox="`0 0 ${WIDTH} ${HEIGHT}`"
      class="w-full"
      @pointermove="onMove"
      @pointerleave="hoverIndex = null"
    >
      <line
        v-for="fraction in [0, 0.5, 1]"
        :key="fraction"
        :x1="PAD"
        :x2="WIDTH - PAD"
        :y1="PAD + fraction * plotHeight"
        :y2="PAD + fraction * plotHeight"
        class="stroke-surface-200 dark:stroke-surface-700"
        stroke-width="1"
      />
      <line
        v-if="hoverPoint"
        :x1="hoverPoint.px"
        :x2="hoverPoint.px"
        :y1="PAD"
        :y2="HEIGHT - PAD"
        class="stroke-surface-300 dark:stroke-surface-600"
        stroke-width="1"
      />
      <polyline
        :points="polyline"
        fill="none"
        :stroke="color"
        stroke-width="2"
        stroke-linejoin="round"
        stroke-linecap="round"
      />
      <circle
        v-if="focusPoint"
        :cx="focusPoint.px"
        :cy="focusPoint.py"
        r="3.5"
        :fill="color"
        stroke="var(--p-content-background)"
        stroke-width="1.5"
      />
      <text :x="PAD" :y="PAD - 3" class="text-xs text-muted-color" fill="currentColor">
        {{ format(bounds.max) }}
      </text>
      <text :x="PAD" :y="HEIGHT - 2" class="text-xs text-muted-color" fill="currentColor">
        {{ format(bounds.min) }}
      </text>
    </svg>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

const props = defineProps<{
  name: string
  points: [number, number][]
  color: string
}>()

const WIDTH = 320
const HEIGHT = 88
const PAD = 12

const plotHeight = HEIGHT - PAD * 2

const hoverIndex = ref<number | null>(null)

const bounds = computed(() => {
  const ys = props.points.map(([, y]) => y)
  const min = ys.length ? Math.min(...ys) : 0
  const max = ys.length ? Math.max(...ys) : 1
  return { min, max, span: max - min || 1 }
})

const project = (index: number): { px: number; py: number } => {
  const [, y] = props.points[index]
  const px = PAD + (index / Math.max(1, props.points.length - 1)) * (WIDTH - PAD * 2)
  const py = HEIGHT - PAD - ((y - bounds.value.min) / bounds.value.span) * plotHeight
  return { px, py }
}

const polyline = computed(() =>
  props.points.map((_, index) => `${project(index).px},${project(index).py}`).join(' '),
)

const hoverPoint = computed(() =>
  hoverIndex.value === null || !props.points.length ? null : project(hoverIndex.value),
)

const focusPoint = computed(() => {
  if (!props.points.length) return null
  return hoverPoint.value ?? project(props.points.length - 1)
})

const format = (value: number): string =>
  Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(3)

const readout = computed(() => {
  if (!props.points.length) return ''
  const index = hoverIndex.value ?? props.points.length - 1
  const [x, y] = props.points[index]
  return hoverIndex.value === null ? format(y) : `${x} · ${format(y)}`
})

const onMove = (event: PointerEvent): void => {
  const rect = (event.currentTarget as SVGSVGElement).getBoundingClientRect()
  if (rect.width <= 0 || props.points.length < 2) return
  const fraction = (event.clientX - rect.left) / rect.width
  hoverIndex.value = Math.max(
    0,
    Math.min(props.points.length - 1, Math.round(fraction * (props.points.length - 1))),
  )
}
</script>
