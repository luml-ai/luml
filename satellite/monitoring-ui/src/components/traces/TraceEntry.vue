<template>
  <div class="entry">
    <header class="header">
      <h4 class="title">{{ title }}</h4>
      <span v-if="stats" class="stats">{{ stats }}</span>
    </header>
    <div class="value" :class="{ code: !!stats }">
      <pre v-if="stats" class="text">{{ text }}</pre>
      <span v-else class="text">{{ text }}</span>
      <MCopyButton class="copy" :text="text" :label="title" :icon-size="14" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { formatTraceValue, getTraceValueStats } from '@/utils/traces'
import MCopyButton from '@/components/MCopyButton.vue'

interface Props {
  title: string
  value: unknown
}

const props = defineProps<Props>()

const text = computed(() => formatTraceValue(props.value))

const stats = computed(() => getTraceValueStats(text.value))
</script>

<style scoped>
.entry {
  display: flex;
  flex-shrink: 0;
  flex-direction: column;
  gap: 10px;
  padding: 16px;
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  background: var(--p-content-background);
}

.header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--p-divider-border-color);
}

.title {
  flex: 1;
  min-width: 0;
  margin: 0;
  font-size: 16px;
  font-weight: 500;
  color: var(--p-text-color);
  overflow-wrap: anywhere;
}

.stats {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--p-text-muted-color);
  white-space: nowrap;
}

.value {
  position: relative;
  padding: 8px 40px 8px 12px;
  border: 1px solid var(--p-content-border-color);
  border-radius: 6px;
  background: var(--p-card-background);
}

.text {
  display: block;
  margin: 0;
  font-size: 13px;
  color: var(--p-text-color);
  overflow-wrap: anywhere;
}

.code .text {
  font-family: 'IBM Plex Mono', Consolas, 'SFMono-Regular', Menlo, monospace;
  font-size: 12px;
  white-space: pre-wrap;
}

.copy {
  position: absolute;
  top: 8px;
  right: 8px;
}
</style>
