<template>
  <div v-tooltip="name" :style="columnBodyStyle + 'width: 180px'">
    {{ name }}
  </div>
  <div class="id-row">
    <span class="id-text">Id: </span>
    <UiId :id="id" class="id-value"></UiId>
  </div>
</template>

<script setup lang="ts">
import UiId from '@/components/ui/UiId.vue'

type Props = {
  name: string
  id: string
  columnBodyStyle: string
}

const props = defineProps<Props>()
</script>

<style scoped>
.id-row {
  font-size: 12px;
}

.id-text {
  color: var(--p-text-muted-color);
}
</style>
