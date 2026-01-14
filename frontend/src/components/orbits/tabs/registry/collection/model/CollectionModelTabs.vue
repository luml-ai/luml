<template>
  <Tabs :value="$route.name as string">
    <TabList :pt="tabsListPT">
      <Tab
        :pt="tabPT"
        v-for="tab in items"
        :key="tab.label"
        :value="tab.routeName"
        :disabled="tab.disabled"
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
import { LayoutDashboard, FileChartLine, ScanEye, Paperclip } from 'lucide-vue-next'
import { computed } from 'vue'

type Props = {
  showModelCard: boolean
  showExperimentSnapshot: boolean
  showModelAttachments: boolean
}

const tabsListPT = {
  tabList: { style: 'border-left: none; border-top: none; border-right: none;' },
}

const tabPT: TabPassThroughOptions = {}

const props = defineProps<Props>()

const items = computed(() => [
  {
    label: 'Overview',
    routeName: 'model',
    icon: LayoutDashboard,
  },
  {
    label: 'Model card',
    routeName: 'model-card',
    icon: FileChartLine,
    disabled: !props.showModelCard,
  },
  {
    label: 'Experiment snapshot',
    routeName: 'model-snapshot',
    icon: ScanEye,
    disabled: !props.showExperimentSnapshot,
  },
  {
    label: 'Attachments',
    routeName: 'model-attachments',
    icon: Paperclip,
    disabled: !props.showModelAttachments,
  },
])
</script>

<style scoped>
.tab {
  border: none;
  display: flex;
  align-items: center;
  gap: 7px;
}
</style>
