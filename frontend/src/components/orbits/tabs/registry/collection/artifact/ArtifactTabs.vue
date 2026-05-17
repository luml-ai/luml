<template>
  <Tabs :value="$route.name as string">
    <TabList :pt="tabsListPT">
      <template v-for="tab in items" :key="tab.label">
        <Tab
          v-if="tab.visible"
          :pt="tabPT"
          :value="tab.routeName"
          :disabled="tab.disabled"
          class="tab"
          @click="$router.push({ name: tab.routeName })"
        >
          <RouterLink v-if="tab.routeName" :to="{ name: tab.routeName }" class="tab-link">
            <component :is="tab.icon" :size="14" />
            <span>{{ tab.label }}</span>
          </RouterLink>
        </Tab>
      </template>
    </TabList>
  </Tabs>
</template>

<script setup lang="ts">
import { Tabs, TabList, Tab, type TabPassThroughOptions } from 'primevue'
import { LayoutDashboard, FileChartLine, ScanEye, Paperclip, Database } from 'lucide-vue-next'
import { computed } from 'vue'

type Props = {
  showDataTab: boolean
  showCard: boolean
  showExperimentSnapshot: boolean
  showModelAttachments: boolean

  cardDisabled: boolean
  experimentSnapshotDisabled: boolean
  modelAttachmentsDisabled: boolean
}

const tabsListPT = {
  tabList: { style: 'border-left: none; border-top: none; border-right: none;' },
}

const tabPT: TabPassThroughOptions = {}

const props = defineProps<Props>()

const items = computed(() => [
  {
    label: 'Overview',
    routeName: 'artifact',
    icon: LayoutDashboard,
    visible: true,
  },
  {
    label: 'Data',
    routeName: 'dataset',
    icon: Database,
    visible: props.showDataTab,
  },
  {
    label: 'Card',
    routeName: 'artifact-card',
    icon: FileChartLine,
    visible: props.showCard,
    disabled: props.cardDisabled,
  },
  {
    label: 'Experiment snapshot',
    routeName: 'experiment-snapshot',
    icon: ScanEye,
    visible: props.showExperimentSnapshot,
    disabled: props.experimentSnapshotDisabled,
  },
  {
    label: 'Attachments',
    routeName: 'attachments',
    icon: Paperclip,
    visible: props.showModelAttachments,
    disabled: props.modelAttachmentsDisabled,
  },
])
</script>

<style scoped>
.tab {
  border: none;
}

.tab-link {
  color: inherit;
  text-decoration: none;
  display: flex;
  align-items: center;
  gap: 7px;
}
</style>
