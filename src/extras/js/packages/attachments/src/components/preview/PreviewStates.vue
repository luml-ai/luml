<template>
  <div class="preview-state">
    <div v-if="state === 'empty'" class="state-content empty">
      <span>File is empty</span>
    </div>

    <div v-else-if="state === 'too-big'" class="state-content warning">
      <span>File is too large for preview</span>
    </div>

    <div v-else-if="state === 'unsupported'" class="state-content warning">
      <span>This file type is not supported for preview</span>
    </div>

    <div v-else-if="state === 'error'" class="state-content error">
      <span>{{ errorMessage || 'Failed to load preview' }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { PreviewStatesProps } from '../../interfaces/interfaces'

defineProps<PreviewStatesProps>()
</script>

<style scoped>
.preview-state {
  flex: 1;
  display: flex;
  height: 100%;
}
.state-content {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  padding: 1rem;
  color: var(--p-text-muted-color);
}
</style>
