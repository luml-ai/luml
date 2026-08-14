<template>
  <div ref="scroller" class="h-full overflow-auto rail-scroll">
    <svg :width="layout.width" :height="layout.height" class="block">
      <g v-for="lane in layout.lanes" :key="lane.branchId" :opacity="laneOpacity(lane)">
        <path
          v-if="lane.fork"
          :d="forkPath(lane)"
          fill="none"
          :stroke="lane.color"
          :stroke-width="lane.branchId === currentBranchId ? 2.5 : 1.5"
          stroke-linecap="round"
        />
        <line
          v-if="lane.bottomY > lane.topY"
          :x1="lane.x"
          :y1="lane.topY"
          :x2="lane.x"
          :y2="lane.bottomY"
          :stroke="lane.color"
          :stroke-width="lane.branchId === currentBranchId ? 2.5 : 1.5"
          stroke-linecap="round"
        />
      </g>

      <circle
        v-if="marker"
        :cx="marker.x"
        :cy="marker.y"
        r="9"
        fill="none"
        :stroke="marker.color"
        stroke-width="2"
      />

      <g
        v-for="stop in layout.stops"
        :key="stop.key"
        class="cursor-pointer rail-stop"
        :opacity="stopOpacity(stop)"
        @click="emit('select', stop.branchId, stop.step)"
      >
        <title>step {{ stop.step }} · {{ stop.detail }} · {{ stop.label }}</title>
        <circle :cx="stop.x" :cy="stop.y" r="13" fill="transparent" />
        <circle
          v-if="stop.liveHead"
          class="rail-ping"
          :cx="stop.x"
          :cy="stop.y"
          r="9"
          fill="none"
          :stroke="laneColor(stop.branchId)"
          stroke-width="2"
        />
        <circle
          class="rail-dot"
          :cx="stop.x"
          :cy="stop.y"
          :r="stop.kind === 'checkpoint' ? 5 : 3"
          :fill="stop.kind === 'checkpoint' ? laneColor(stop.branchId) : 'var(--p-content-background)'"
          :stroke="stop.failed ? 'var(--p-red-500)' : stop.kind === 'checkpoint' ? 'var(--p-content-background)' : laneColor(stop.branchId)"
          stroke-width="1.5"
        />
        <text
          v-if="showLaneNames && stop.laneHead && stop.branchId !== currentBranchId && !selectedLabelYs.has(stop.y)"
          :x="stop.x + 11"
          :y="stop.y + 4"
          class="text-xs font-medium rail-halo"
          :fill="laneColor(stop.branchId)"
        >
          {{ laneName(stop.branchId) }}
        </text>
        <text
          v-if="stop.branchId === currentBranchId"
          :x="layout.labelX"
          :y="stop.y + 4"
          class="text-xs"
          :class="stop.kind === 'checkpoint' ? '' : 'text-muted-color'"
          fill="currentColor"
        >
          {{ truncate(stop.label) }}
        </text>
      </g>
    </svg>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { buildRailLayout, ROW_HEIGHT, type RailLane, type RailStop } from './railLayout'
import type { BranchId, FlowSession } from '../../types'

/**
 * The rail, drawn: lanes are forks, time flows down, stops are checkpoints.
 *
 * It receives the *full* session — not the playback-filtered one — so every
 * position is fixed for the life of the session. Selection and playback change
 * emphasis and opacity only; stops beyond the current step render hollow, which
 * is what makes the same drawing double as the scrubber.
 */
const props = defineProps<{
  session: FlowSession
  currentBranchId: BranchId
  currentStep: number
}>()

const emit = defineEmits<{ select: [BranchId, number] }>()

const scroller = ref<HTMLDivElement | null>(null)

const layout = computed(() => buildRailLayout(props.session))

const showLaneNames = computed(() => layout.value.lanes.length <= 8)

// A lane name that lands on the same row as a selected-lane label would collide
// with it in the label column — visibility may change, position may not.
const selectedLabelYs = computed(
  () =>
    new Set(
      layout.value.stops
        .filter((stop) => stop.branchId === props.currentBranchId)
        .map((stop) => stop.y),
    ),
)

const laneById = computed(() => new Map(layout.value.lanes.map((lane) => [lane.branchId, lane])))
const laneColor = (branchId: BranchId): string => laneById.value.get(branchId)?.color ?? 'currentColor'
const laneName = (branchId: BranchId): string => laneById.value.get(branchId)?.name ?? branchId

const laneOpacity = (lane: RailLane): number => {
  if (lane.branchId === props.currentBranchId) return 1
  if (lane.startStep > props.currentStep) return 0.15
  return 0.4
}

const stopOpacity = (stop: RailStop): number => {
  if (stop.step > props.currentStep) return 0.25
  return stop.branchId === props.currentBranchId ? 1 : 0.55
}

const forkPath = (lane: RailLane): string => {
  if (!lane.fork) return ''
  const { parentX, y } = lane.fork
  const lift = ROW_HEIGHT * 0.6
  return `M ${parentX} ${y - lift} C ${parentX} ${y}, ${lane.x} ${y - lift}, ${lane.x} ${y}`
}

const marker = computed<{ x: number; y: number; color: string } | null>(() => {
  const lane = laneById.value.get(props.currentBranchId)
  if (!lane) return null
  let y = lane.topY
  for (const row of layout.value.stepYs) {
    if (row.step > props.currentStep) break
    y = row.y
  }
  y = Math.min(Math.max(y, lane.topY), lane.bottomY)
  return { x: lane.x, y, color: lane.color }
})

const truncate = (text: string): string => (text.length > 36 ? `${text.slice(0, 35)}…` : text)

// Keep the playback marker in view while playing or after a seek. Assigning
// scrollTop directly stays silent under jsdom, where scrollTo is unimplemented.
watch(
  () => [props.currentStep, props.currentBranchId] as const,
  () => {
    const el = scroller.value
    const position = marker.value
    if (!el || !position || el.clientHeight === 0) return
    const target = position.y - el.clientHeight / 2
    el.scrollTop = Math.max(0, Math.min(target, el.scrollHeight - el.clientHeight))
  },
)
</script>

<style scoped>
.rail-scroll {
  scroll-behavior: smooth;
}

.rail-stop:hover .rail-dot {
  stroke-width: 3;
}

.rail-halo {
  paint-order: stroke;
  stroke: var(--p-content-background);
  stroke-width: 3px;
}

@keyframes rail-ping {
  0% {
    opacity: 0.9;
  }
  70% {
    opacity: 0;
  }
  100% {
    opacity: 0;
  }
}

.rail-ping {
  animation: rail-ping 1.8s ease-out infinite;
}

@media (prefers-reduced-motion: reduce) {
  .rail-ping {
    animation: none;
    opacity: 0.5;
  }
  .rail-scroll {
    scroll-behavior: auto;
  }
}
</style>
