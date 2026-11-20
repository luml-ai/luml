<template>
  <div class="entries">
    <TraceEntry
      v-for="(entry, index) in entries"
      :key="`${index}:${entry.key}`"
      :title="entry.key"
      :value="entry.value"
    />
    <MEmpty v-if="!entries.length" :title="emptyTitle" />
  </div>
</template>

<script setup lang="ts">
import type { TraceEntry as TraceEntryItem } from '@/types/traces'
import MEmpty from '@/components/MEmpty.vue'
import TraceEntry from '@/components/traces/TraceEntry.vue'

interface Props {
  entries: TraceEntryItem[]
  emptyTitle: string
}

defineProps<Props>()
</script>

<style scoped>
.entries {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 5px;
  min-height: 0;
  padding: 12px 20px 20px;
  overflow-y: auto;
}
</style>
