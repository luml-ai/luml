<template>
  <div class="body">
    <header class="header">
      <TraceSpanTitle :span="span" size="large" />
    </header>
    <Tabs v-model:value="tab" class="tabs">
      <TabList>
        <Tab v-for="item in TRACE_DETAIL_TABS" :key="item.value" :value="item.value">
          {{ item.label }}
        </Tab>
      </TabList>
    </Tabs>
    <TraceEntries :entries="entries" :empty-title="emptyTitle" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import type { TraceSpan } from '@/api/monitoring/interfaces'
import { TRACE_DETAIL_TABS, TraceDetailTab } from '@/constants/traces'
import { getEventEntries, getSortedEntries, getSpanMetadata } from '@/utils/traces'
import TraceSpanTitle from '@/components/traces/TraceSpanTitle.vue'
import TraceEntries from '@/components/traces/TraceEntries.vue'

interface Props {
  span: TraceSpan
}

const props = defineProps<Props>()

const tab = ref<string | number>(TraceDetailTab.ATTRIBUTES)

const entries = computed(() => {
  if (tab.value === TraceDetailTab.EVENTS) return getEventEntries(props.span.events)
  if (tab.value === TraceDetailTab.METADATA) return getSpanMetadata(props.span)
  return getSortedEntries(props.span.attributes)
})

const emptyTitle = computed(() => {
  if (tab.value === TraceDetailTab.EVENTS) return 'No events recorded'
  if (tab.value === TraceDetailTab.METADATA) return 'No metadata recorded'
  return 'No attributes recorded'
})
</script>

<style scoped>
.body {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  padding-top: 20px;
  overflow: hidden;
}

.header {
  padding: 8px 20px;
  border-bottom: 1px solid var(--p-divider-border-color);
}

.tabs {
  flex-shrink: 0;
}
</style>
