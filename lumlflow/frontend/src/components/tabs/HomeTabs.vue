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
import { FlaskConical, Folder } from 'lucide-vue-next'
import { Tabs, TabList, Tab, type TabListPassThroughOptions } from 'primevue'
import { useRoute } from 'vue-router'
import { computed } from 'vue'

const TABLIST_PT: TabListPassThroughOptions = {
  tabList: { style: 'border-left: none; border-top: none; border-right: none;' },
}

const items = [
  {
    label: 'Experiments',
    route: { name: ROUTE_NAMES.EXPERIMENTS },
    icon: FlaskConical,
  },
  {
    label: 'Workspace',
    route: { name: ROUTE_NAMES.WORKSPACES },
    icon: Folder,
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
