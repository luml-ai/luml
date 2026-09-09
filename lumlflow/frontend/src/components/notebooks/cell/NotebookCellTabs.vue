<template>
  <Tabs :value="modelValue" @update:value="updateValue">
    <TabList :pt="CELL_TABS_LIST_PT">
      <Tab v-for="tab in NOTEBOOK_CELL_TABS" :key="tab.label" :value="tab.value" class="tab">
        <component :is="tab.icon" :size="14" />
        <span>{{ tab.label }}</span>
      </Tab>
    </TabList>
  </Tabs>
</template>

<script setup lang="ts">
import { Tabs, TabList, Tab } from 'primevue'
import { CELL_TABS_LIST_PT, NOTEBOOK_CELL_TABS } from '@/components/notebooks/cell/cell.const'

const modelValue = defineModel<string>('modelValue', { required: true })

function updateValue(value: string | number) {
  modelValue.value = String(value)
}
</script>

<style scoped>
@reference "@/assets/css/index.css";

.tab {
  @apply border-none flex items-center gap-1.5 px-2 py-1;
}
</style>
