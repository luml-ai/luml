<template>
  <svg class="vue-flow__marker vue-flow__container">
    <defs>
      <marker
        :id="id"
        viewBox="-2 -6.5 4 13"
        refX="0"
        refY="0"
        :markerWidth="width"
        :markerHeight="height"
        markerUnits="strokeWidth"
        orient="auto-start-reverse"
      >
        <rect x="-2" y="-6.5" width="4" height="13" rx="2" ry="2" :fill="fill" />
      </marker>

      <marker
        :id="`${id}-arrow`"
        viewBox="0 0 30 30"
        refX="15"
        refY="12"
        :markerWidth="markerWidth * 4"
        :markerHeight="markerWidth * 4"
        markerUnits="strokeWidth"
        orient="auto"
      >
        <path
          d="m9 18 6-6-6-6"
          :stroke="arrowFill"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          fill="none"
        />
      </marker>
    </defs>
  </svg>
</template>

<script setup lang="ts">
type Props = {
  id: string
  stroke?: string
  fill?: string
  arrowFill?: string
  strokeWidth?: number
  width?: number
  height?: number
  markerWidth?: number
}

withDefaults(defineProps<Props>(), {
  stroke: 'var(--p-surface-500)',
  fill: 'var(--p-surface-500)',
  arrowFill: 'var(--p-organizationchart-connector-color)',
  strokeWidth: 2,
  width: 2,
  height: 6.5,
  markerWidth: 4,
})
</script>
