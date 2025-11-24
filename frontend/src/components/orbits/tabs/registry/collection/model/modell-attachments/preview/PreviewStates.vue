<template>
  <div class="preview-state">
    <div v-if="state === 'loading'" class="loading-state">
      <progress-spinner style="width: 48px; height: 48px" />
      <span class="mt-2">Loading...</span>
    </div>

    <div v-else-if="errorMessage === 'too-big'" class="state-text">
      <p>This file is too big for preview.</p>
    </div>

    <div v-else-if="state === 'error'" class="content">
      <BadgeX width="48" height="48" class="icon error" />
      <div class="title">{{ errorMessage }}</div>
    </div>

    <div v-else-if="state === 'unsupported'" class="state-text">
      <p>This format is not supported for preview.</p>
    </div>

    <div v-else-if="state === 'empty'" class="state-text">
      <p>This attachment is empty.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import ProgressSpinner from 'primevue/progressspinner'
import { BadgeX } from 'lucide-vue-next'

defineProps<{
  state: 'loading' | 'error' | 'unsupported' | 'too-big' | 'empty'
  errorMessage?: string
}>()
</script>

<style scoped>
.preview-state {
  flex: 1;
  display: flex;
  height: 100%;
}

.state-text {
  display: left;
  color: var(--p-form-field-float-label-color);
}

.loading-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  color: var(--text-color-secondary);
}

.content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  text-align: center;
  font-weight: 500;
}

.icon {
  flex: 0 0 auto;
  color: var(--p-text-link-color);
}

.icon.error {
  color: var(--p-badge-danger-background);
}

.title {
  font-size: 16px;
  font-weight: 500;
  color: var(--p-form-field-float-label-color);
}
</style>
