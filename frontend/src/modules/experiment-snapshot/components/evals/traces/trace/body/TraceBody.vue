<template>
  <div class="content">
    <header class="header">
      <h4 class="title">
        <component :is="spanTypeData.icon" :size="16" :color="spanTypeData.color" />
        <span>{{ data.name }}</span>
      </h4>
      <div class="info">
        <History :size="12" />
        <span>{{ time }}</span>
      </div>
    </header>
    <Tabs v-model:value="currentTab" class="tabs">
      <TabList class="tabs-list" :pt="{ tabList: 'tabs-list' }">
        <Tab :value="0" class="tab">Attributes</Tab>
        <Tab :value="1" class="tab">Events</Tab>
        <Tab :value="2" class="tab">Metadata</Tab>
      </TabList>
      <TabPanels class="tabs-panels">
        <TabPanel :value="0">
          <div v-if="sortedAttributes" class="items">
            <UiMultiTypeText
              v-for="[key, value] in sortedAttributes"
              :key="key"
              :title="key"
              :text="value"
            ></UiMultiTypeText>
          </div>
          <div v-else>Attributes not found.</div>
        </TabPanel>
        <TabPanel :value="1">
          <div v-if="sortedEvents" class="items">
            <UiMultiTypeText
              v-for="[key, value] in sortedEvents"
              :key="key"
              :title="key"
              :text="value"
            >
            </UiMultiTypeText>
          </div>
          <div v-else>Events not found.</div></TabPanel
        >
        <TabPanel :value="2">
          <div v-if="data.attributes" class="items"></div>
          <div v-else>Metadata not found.</div>
        </TabPanel>
      </TabPanels>
    </Tabs>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { History } from 'lucide-vue-next'
import { Tabs, TabList, Tab, TabPanels, TabPanel } from 'primevue'
import UiMultiTypeText from '../../../../ui/UiMultiTypeText.vue'
import type { TraceSpan } from '@/modules/experiment-snapshot/interfaces/interfaces'
import { getFormattedTime, getSpanTypeData } from '@/modules/experiment-snapshot/helpers/helpers'

type Props = {
  data: TraceSpan
}

const props = defineProps<Props>()

const currentTab = ref(0)

const spanTypeData = computed(() => {
  return getSpanTypeData(props.data.dfs_span_type)
})

const time = computed(() => {
  return getFormattedTime(props.data.start_time_unix_nano, props.data.end_time_unix_nano)
})

const sortedAttributes = computed(() => {
  if (!props.data.attributes) return null
  return Object.entries(props.data.attributes).sort((a, b) => {
    return a[0].localeCompare(b[0], undefined, { numeric: true, sensitivity: 'base' })
  })
})

const sortedEvents = computed(() => {
  if (!props.data.events) return null
  return Object.entries(props.data.events).sort((a, b) => {
    return a[0].localeCompare(b[0], undefined, { numeric: true, sensitivity: 'base' })
  })
})
</script>

<style scoped>
.content {
  display: flex;
  flex-direction: column;
}
.header {
  padding: 8px 20px;
  margin-bottom: 8px;
}
.title {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.info {
  padding-left: 8px;
  display: flex;
  gap: 4px;
  align-items: center;
  color: var(--p-text-muted-color);
  font-size: 12px;
  margin-bottom: 8px;
}
.tabs {
  flex: 1 1 auto;
  overflow: hidden;
}
:deep(.tabs-list) {
  border-left: none;
  border-top: none;
  border-right: none;
  background-color: transparent;
}
.tabs-panels {
  padding: 20px;
  background-color: transparent;
  flex: 1 1 auto;
  overflow-y: auto;
}
.tab {
  border: none;
}
.items {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>
