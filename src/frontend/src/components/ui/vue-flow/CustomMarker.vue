<template>
  <svg class="vue-flow__marker vue-flow__container">
    <defs>
      <marker
        :id="id"
        class="vue-flow__arrowhead"
        viewBox="-2 -6.5 4 13"
        refX="0"
        refY="0"
        :markerWidth="width"
        :markerHeight="height"
        markerUnits="strokeWidth"
        orient="auto-start-reverse"
      >
        <rect
          x="-2"
          y="-6.5"
          width="4"
          height="13"
          rx="2"
          ry="2"
          :fill="fill"
          d="M -2 -6.5 H 2 V 6.5 H -2 Z"
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
  strokeWidth?: number
  width?: number
  height?: number
}

withDefaults(defineProps<Props>(), {
  stroke: 'var(--p-surface-500)',
  fill: 'var(--p-surface-500)',
  strokeWidth: 2,
  width: 2,
  height: 6.5,
})
</script>

<style scoped></style>
