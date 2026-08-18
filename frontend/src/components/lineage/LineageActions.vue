<template>
  <div class="buttons">
    <Button
      severity="secondary"
      class="light-button"
      :disabled="lineageStore.history.length === 0"
      @click="resetPositions"
    >
      Reset positions <RotateCcw :size="14" />
    </Button>
    <Button severity="secondary" class="light-button" @click="toggleMaximized">
      <template #icon>
        <component :is="scaleIcon" :size="14" />
      </template>
    </Button>
  </div>
</template>

<script setup lang="ts">
import { Maximize2, Minimize2, RotateCcw } from 'lucide-vue-next'
import { Button } from 'primevue'
import { computed } from 'vue'
import { useLineageStore } from '@/stores/lineage'

const lineageStore = useLineageStore()

const isMaximized = defineModel('isMaximized', { default: false })

const scaleIcon = computed(() => {
  return isMaximized.value ? Minimize2 : Maximize2
})

function toggleMaximized() {
  isMaximized.value = !isMaximized.value
}

function resetPositions() {
  lineageStore.resetPositions()
}
</script>

<style scoped>
.light-button {
  background-color: var(--p-card-background) !important;
  border-color: transparent;
  box-shadow: var(--card-shadow);
}
.buttons {
  display: flex;
  align-items: center;
  gap: 8px;
}
</style>
