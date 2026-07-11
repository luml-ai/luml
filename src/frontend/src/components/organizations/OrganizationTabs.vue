<template>
  <Tabs :value="route.name as string">
    <TabList :pt="tabsListPT">
      <Tab
        :pt="tabPT"
        v-for="tab in items"
        :key="tab.label"
        :value="tab.routeName"
        class="tab"
        @click="$router.push({ name: tab.routeName })"
      >
        <component :is="tab.icon" :size="14" />
        <span>{{ tab.label }}</span>
      </Tab>
    </TabList>
  </Tabs>
</template>

<script setup lang="ts">
import { Tabs, TabList, Tab, type TabPassThroughOptions } from 'primevue'
import { Users, Orbit, FolderDot } from 'lucide-vue-next'
import { useRoute } from 'vue-router'

const tabsListPT = {
  tabList: { style: 'border-left: none; border-top: none; border-right: none;' },
}

const tabPT: TabPassThroughOptions = {}

const items = [
  {
    label: 'Members',
    routeName: 'organization-members',
    icon: Users,
  },
  {
    label: 'Orbits',
    routeName: 'organization-orbits',
    icon: Orbit,
  },
  {
    label: 'Buckets',
    routeName: 'organization-buckets',
    icon: FolderDot,
  },
]

const route = useRoute()
</script>

<style scoped>
.tab {
  border: none;
  display: flex;
  align-items: center;
  gap: 7px;
}
</style>
