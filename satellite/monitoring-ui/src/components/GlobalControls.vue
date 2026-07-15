<template>
  <div class="controls" data-testid="global-controls">
    <div class="control">
      <span class="control-label">Window</span>
      <div class="segmented" role="group" aria-label="Window">
        <button
          v-for="option in windowOptions"
          :key="option"
          type="button"
          class="segment"
          :class="{ active: dimensions.window === option }"
          :data-testid="`window-${option}`"
          @click="$emit('update:window', option)"
        >
          {{ option }}
        </button>
      </div>
    </div>

    <div class="control">
      <span class="control-label">Compare</span>
      <div class="segmented" role="group" aria-label="Compare">
        <button
          v-for="option in compareOptions"
          :key="option"
          type="button"
          class="segment"
          :class="{ active: dimensions.compare === option }"
          :data-testid="`compare-${option}`"
          @click="$emit('update:compare', option)"
        >
          {{ option }}
        </button>
      </div>
    </div>

    <div class="control">
      <span class="control-label">Severity</span>
      <div class="segmented" role="group" aria-label="Severity">
        <button
          v-for="option in severityOptions"
          :key="option"
          type="button"
          class="segment"
          :class="{ active: dimensions.severity === option }"
          :data-testid="`severity-${option}`"
          @click="$emit('update:severity', option)"
        >
          {{ option }}
        </button>
      </div>
    </div>

    <button type="button" class="refresh" data-testid="refresh" @click="$emit('refresh')">
      <RefreshCw :size="14" />
      Refresh
    </button>
  </div>
</template>

<script setup lang="ts">
import { RefreshCw } from 'lucide-vue-next'
import { Compare, SeverityFilter, Window, type Dimensions } from '@/api/types'

defineProps<{ dimensions: Dimensions }>()
defineEmits<{
  'update:window': [Window]
  'update:compare': [Compare]
  'update:severity': [SeverityFilter]
  refresh: []
}>()

const windowOptions = [Window.H24, Window.D7, Window.D30]
const compareOptions = [Compare.REFERENCE, Compare.PREVIOUS]
const severityOptions = [SeverityFilter.ALL, SeverityFilter.WARNING, SeverityFilter.CRITICAL]
</script>

<style scoped>
.controls {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--luml-space-5);
}
.control {
  display: flex;
  align-items: center;
  gap: var(--luml-space-3);
}
.control-label {
  font-size: 13px;
  color: var(--luml-fg-muted);
}
.segmented {
  display: inline-flex;
  border: 1px solid var(--luml-border);
  border-radius: var(--luml-radius-md);
  overflow: hidden;
  background: var(--luml-bg-card);
}
.segment {
  border: none;
  background: transparent;
  padding: 7px 14px;
  font: inherit;
  font-size: 13px;
  color: var(--luml-fg);
  cursor: pointer;
  text-transform: capitalize;
}
.segment + .segment {
  border-left: 1px solid var(--luml-border);
}
.segment.active {
  background: var(--luml-brand);
  color: var(--luml-brand-contrast);
  font-weight: 500;
}
.refresh {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin-left: auto;
  padding: 7px 14px;
  border: 1px solid var(--luml-border);
  border-radius: var(--luml-radius-md);
  background: var(--luml-bg-card);
  color: var(--luml-fg);
  font: inherit;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
}
.refresh:hover {
  background: var(--luml-bg-hover);
}
</style>
