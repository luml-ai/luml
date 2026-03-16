<template>
  <div v-tooltip.top="data.name" class="cell" style="width: 123px">
    <span class="circle" :style="{ backgroundColor: data.color }"></span>
    {{ data.name }}
  </div>
</template>

<script setup lang="ts">
import type { ModelIdColumnProps } from './interface'

defineProps<ModelIdColumnProps>()
</script>

<style scoped>
.cell {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

.circle {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex: 0 0 auto;
  margin-bottom: -2px;
}
</style>
