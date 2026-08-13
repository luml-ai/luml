<template>
  <div class="body" data-testid="trace-span-body">
    <header class="head">
      <h4 class="title">
        <component :is="spanTypeData.icon" :size="16" :color="spanTypeData.color" />
        <span>{{ data.name }}</span>
      </h4>
      <div class="info">
        <History :size="12" />
        <span>{{ time }}</span>
      </div>
    </header>

    <div class="tabs" role="tablist">
      <button
        v-for="tab in TABS"
        :key="tab"
        type="button"
        role="tab"
        class="tab"
        :class="{ active: currentTab === tab }"
        :aria-selected="currentTab === tab"
        :data-testid="`trace-tab-${tab.toLowerCase()}`"
        @click="currentTab = tab"
      >
        {{ tab }}
      </button>
    </div>

    <div class="panel">
      <template v-if="currentTab === 'Attributes'">
        <div v-if="sortedAttributes.length" class="items">
          <div v-for="[key, value] in sortedAttributes" :key="key" class="entry">
            <p class="key">{{ key }}</p>
            <pre class="mono value">{{ stringify(value) }}</pre>
          </div>
        </div>
        <p v-else class="empty">Attributes not found.</p>
      </template>

      <template v-else-if="currentTab === 'Events'">
        <div v-if="data.events.length" class="items">
          <div v-for="(event, index) in data.events" :key="index" class="entry">
            <p class="key">{{ index }}</p>
            <pre class="mono value">{{ stringify(event) }}</pre>
          </div>
        </div>
        <p v-else class="empty">Events not found.</p>
      </template>

      <template v-else>
        <div class="items">
          <div v-for="[key, value] in metadata" :key="key" class="entry">
            <p class="key">{{ key }}</p>
            <pre class="mono value">{{ value }}</pre>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { History } from 'lucide-vue-next'
import type { TraceSpanNode } from '@/api/types'
import { getFormattedTime, getSpanTypeData } from '@/lib/spans'

const TABS = ['Attributes', 'Events', 'Metadata'] as const
type Tab = (typeof TABS)[number]

const props = defineProps<{ data: TraceSpanNode }>()

const currentTab = ref<Tab>('Attributes')

const spanTypeData = computed(() => getSpanTypeData(props.data.dfs_span_type))

const time = computed(() =>
  getFormattedTime(props.data.start_time_unix_nano, props.data.end_time_unix_nano),
)

const sortedAttributes = computed(() =>
  Object.entries(props.data.attributes ?? {}).sort((a, b) =>
    a[0].localeCompare(b[0], undefined, { numeric: true, sensitivity: 'base' }),
  ),
)

const metadata = computed<[string, string][]>(() => {
  const entries: [string, string][] = [
    ['span_id', props.data.span_id],
    ['trace_id', props.data.trace_id],
    ['kind', String(props.data.kind)],
    ['status_code', props.data.status_code == null ? '—' : String(props.data.status_code)],
  ]
  if (props.data.parent_span_id) entries.push(['parent_span_id', props.data.parent_span_id])
  if (props.data.status_message) entries.push(['status_message', props.data.status_message])
  return entries
})

/** Objects arrive decoded from the API; render them the way the Platform does. */
function stringify(value: unknown): string {
  if (value == null) return '—'
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}
</script>

<style scoped>
.body {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}
.head {
  padding: 0 20px 8px;
}
.title {
  display: flex;
  align-items: center;
  gap: 4px;
  margin: 0 0 4px;
  font-size: 14px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.info {
  padding-left: 8px;
  display: flex;
  gap: 4px;
  align-items: center;
  color: var(--luml-fg-muted);
  font-size: 12px;
}
.tabs {
  display: flex;
  gap: 4px;
  padding: 0 20px;
  border-bottom: 1px solid var(--luml-border);
  flex: 0 0 auto;
}
.tab {
  padding: 8px 12px;
  border: none;
  border-bottom: 2px solid transparent;
  background: transparent;
  color: var(--luml-fg-muted);
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}
.tab:hover {
  color: var(--luml-fg);
}
.tab.active {
  color: var(--luml-fg-strong);
  border-bottom-color: var(--luml-brand, var(--luml-fg-strong));
}
.panel {
  flex: 1 1 auto;
  overflow-y: auto;
  padding: 16px 20px;
}
.items {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.key {
  margin: 0 0 4px;
  font-size: 11px;
  color: var(--luml-fg-muted);
}
.value {
  margin: 0;
  max-height: 220px;
  overflow: auto;
  padding: 8px 10px;
  border: 1px solid var(--luml-surface-100);
  border-radius: var(--luml-radius-md);
  background: var(--luml-surface-100);
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
.empty {
  margin: 0;
  color: var(--luml-fg-muted);
  font-size: 13px;
}
</style>
