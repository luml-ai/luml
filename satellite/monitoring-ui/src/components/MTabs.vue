<template>
  <Tabs :value="tabsStore.activeTab" @update:value="onChange">
    <TabList>
      <Tab v-for="tab in tabsStore.tabs" :key="tab.key" :value="tab.key">
        {{ tab.label }}
      </Tab>
    </TabList>
  </Tabs>
</template>

<script setup lang="ts">
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import { useTabsStore } from '@/store/tabs'
import type { TabKey } from '@/types/tabs'

const tabsStore = useTabsStore()

function onChange(value: string | number) {
  tabsStore.setActiveTab(value as TabKey)
}
</script>
