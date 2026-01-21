<template>
  <div class="app-layout">
    <LayoutHeader />
    <div class="main-container">
      <LayoutSidebar />
      <main class="content-area">
        <div class="content-header">
          <div class="breadcrumbs">
            <span class="breadcrumb-item" disabled>page</span>
            <span class="breadcrumb-separator">></span>
            <span class="breadcrumb-item" disabled>page</span>
            <span class="breadcrumb-separator">></span>
            <span class="breadcrumb-item" disabled>page</span>
          </div>
          <h2>Model details</h2>

          <Tabs :value="$route.name as string">
            <TabList :pt="tabsListPT">
              <Tab
                v-for="tab in items"
                :key="tab.label"
                :value="tab.routeName"
                :disabled="tab.disabled"
                class="tab"
                @click="$router.push({ name: tab.routeName })"
                :pt="tabPT"
              >
                <component :is="tab.icon" :size="14" />
                <span>{{ tab.label }}</span>
              </Tab>
            </TabList>
          </Tabs>
        </div>

        <div class="page-content">
          <slot></slot>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import LayoutHeader from '@/components/layout/LayoutHeader.vue'
import LayoutSidebar from '@/components/layout/LayoutSidebar.vue'
import { Tabs, TabList, Tab, type TabPassThroughOptions } from 'primevue'
import { LayoutDashboard, FolderDot, ScanEye } from 'lucide-vue-next'
import { computed } from 'vue'

type Props = {
  showModelCard?: boolean
  showExperimentSnapshot?: boolean
}

const props = defineProps<Props>()

const tabsListPT = {
  tabList: { style: 'border-left: none; border-top: none; border-right: none;' },
}
const tabPT: TabPassThroughOptions = {}

const items = computed(() => [
  {
    label: 'Overview',
    routeName: 'model',
    icon: LayoutDashboard,
    disabled: true,
  },
  {
    label: 'Model card',
    routeName: 'model-card',
    icon: FolderDot,
    disabled: true,
  },
  {
    label: 'Experiment snapshot',
    routeName: 'model-snapshot',
    icon: ScanEye,
  },
])
</script>

<style scoped>
.main-container {
  display: flex;
  flex-grow: 1;
}

.main-container :deep(.layout-sidebar),
.main-container :deep(aside),
.main-container :deep(nav) {
  padding-top: 5px !important;
}

.content-area {
  flex-grow: 1;
  padding: 24px;
  overflow-y: auto;
}

.content-header {
  margin-bottom: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.tab {
  border: none;
  display: flex;
  align-items: center;
  gap: 7px;
}

.breadcrumbs {
  display: flex;
  align-items: center;
  font-size: 12px;
  gap: 4px;
  margin-bottom: 8px;
  color: #6b7280;
}
</style>
