<template>
  <Tabs :value="modelValue" @update:value="updateValue">
    <TabList :pt="CELL_TABS_LIST_PT">
      <Tab v-for="tab in tabs" :key="tab.id" :value="tab.id" class="tab">
        <component :is="tab.icon" :size="14" />
        <span>{{ tab.label }}</span>
      </Tab>
    </TabList>
  </Tabs>
</template>

<script setup lang="ts">
import type { NotebookCellTabsProps } from '@/components/notebooks/cell/cell.interface'
import { Tabs, TabList, Tab } from 'primevue'
import { CELL_TABS_LIST_PT } from '@/components/notebooks/cell/cell.const'

defineProps<NotebookCellTabsProps>()

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
