<template>
  <div class="message">
    <TriangleAlert :size="16" class="message-icon" />
    <div class="message-content">
      <h3 class="message-title">This stage is already in use by another artifact.</h3>
      <p class="message-description">
        {{ description }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { TrackEntry } from '@/lib/api/orbit-tracks/interfaces'
import { computed } from 'vue'
import { TriangleAlert } from 'lucide-vue-next'

interface Props {
  artifact: TrackEntry
}

const props = defineProps<Props>()

const description = computed(() => {
  return `Once confirmed, the artifact ${props.artifact.artifact_name} will be unlinked from this stage.`
})
</script>

<style scoped>
.message {
  padding: var(--p-toast-content-padding);
  background-color: var(--p-toast-warn-background);
  border-radius: var(--p-toast-border-radius);
  border: var(--p-toast-border-width) solid var(--p-toast-warn-border-color);
  color: var(--p-toast-warn-color);
  display: flex;
  gap: var(--p-toast-content-gap);
}
.message-icon {
  flex: 0 0 auto;
}
.message-content {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  gap: var(--p-toast-text-gap);
}
.message-title {
  font-weight: var(--p-toast-summary-font-weight);
  font-size: var(--p-toast-summary-font-size);
}
.message-description {
  font-weight: var(--p-toast-detail-font-weight);
  font-size: var(--p-toast-detail-font-size);
  color: var(--p-toast-warn-detail-color);
}
</style>
