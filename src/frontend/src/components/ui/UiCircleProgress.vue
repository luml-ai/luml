<template>
  <svg :width="size" :height="size" viewBox="0 0 100 100">
    <circle cx="50" cy="50" r="45" :stroke="secondaryColor" stroke-width="10" fill="none" />

    <circle
      cx="50"
      cy="50"
      r="45"
      :stroke="mainColor"
      stroke-width="10"
      fill="none"
      stroke-linecap="butt"
      :stroke-dasharray="circumference"
      :stroke-dashoffset="circumference - (progress / 100) * circumference"
      transform="rotate(-90 50 50)"
    />
  </svg>
</template>

<script setup lang="ts">
import { defineProps } from 'vue'

type Props = {
  progress: number
  mainColor?: string
  secondaryColor?: string
  size?: number
}

withDefaults(defineProps<Props>(), {
  mainColor: 'var(--p-progressbar-value-background)',
  secondaryColor: 'var(--p-progressbar-background)',
  size: 44,
})

const radius = 45
const circumference = 2 * Math.PI * radius
</script>

<style scoped>
.color {
  color: var(--p-progressbar-value-background);
}
</style>
