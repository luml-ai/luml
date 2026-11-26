<template>
  <Tabs :value="activeLabel">
    <TabList :pt="TABLIST_PT">
      <Tab
        v-for="tab in items"
        :key="tab.label"
        :value="tab.label"
        class="tab"
        @click="select(tab)"
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
import { useRoute, useRouter } from 'vue-router'
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

// With a model the tabs switch local state, so they also work outside the experiment routes.
const model = defineModel<string>()

const route = useRoute()
const router = useRouter()

const activeLabel = computed(
  () => model.value ?? items.find((tab) => tab.route.name === route.name)?.label ?? '',
)

function select(tab: (typeof items)[number]) {
  if (model.value === undefined) router.push(tab.route)
  else model.value = tab.label
}
</script>

<style scoped>
.tab {
  border: none;
  display: flex;
  align-items: center;
  gap: 7px;
}
</style>
