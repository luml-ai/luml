<template>
  <Tabs :value="currentRouteName">
    <TabList :pt="TABLIST_PT">
      <Tab
        v-for="tab in items"
        :key="tab.label"
        :value="tab.route.name"
        class="tab"
        @click="$router.push(tab.route)"
      >
        <component :is="tab.icon" :size="14" />
        <span>{{ tab.label }}</span>
      </Tab>
    </TabList>
  </Tabs>
</template>

<script setup lang="ts">
import { ROUTE_NAMES } from '@/router/router.const'
import { LayoutDashboard, Table2, Braces, Paperclip, ListTree } from 'lucide-vue-next'
import { Tabs, TabList, Tab } from 'primevue'
import { useRoute } from 'vue-router'
import { computed } from 'vue'
import { TABLIST_PT } from './details.const'

const items = [
  {
    label: 'Overview',
    route: { name: ROUTE_NAMES.EXPERIMENT_OVERVIEW },
    icon: LayoutDashboard,
  },
  {
    label: 'Metrics',
    route: { name: ROUTE_NAMES.EXPERIMENT_METRICS },
    icon: Table2,
  },
  {
    label: 'Traces',
    route: { name: ROUTE_NAMES.EXPERIMENT_TRACES },
    icon: ListTree,
  },
  {
    label: 'Evals',
    route: { name: ROUTE_NAMES.EXPERIMENT_EVALS },
    icon: Braces,
  },
  {
    label: 'Attachments',
    route: { name: ROUTE_NAMES.EXPERIMENT_ATTACHMENTS },
    icon: Paperclip,
  },
]

const route = useRoute()

const currentRouteName = computed(() => route.name as string)
</script>

<style scoped>
.tab {
  border: none;
  display: flex;
  align-items: center;
  gap: 7px;
}
</style>
