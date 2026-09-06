<template>
  <Tabs :value="modelValue" @update:value="updateValue">
    <TabList :pt="TABLIST_PT">
      <Tab v-for="tab in items" :key="tab.label" :value="tab.value" class="tab">
        <component :is="tab.icon" :size="14" />
        <span>{{ tab.label }}</span>
      </Tab>
    </TabList>
  </Tabs>
</template>

<script setup lang="ts">
import { ChartSpline, CodeXml, Scroll } from 'lucide-vue-next'
import { Tabs, TabList, Tab, type TabListPassThroughOptions } from 'primevue'

const TABLIST_PT: TabListPassThroughOptions = {
  root: {
    class: 'bg-transparent!',
  },
  tabList: {
    style: 'border-left: none; border-top: none; border-right: none; ',
  },
}

const items = [
  {
    label: 'Plot',
    icon: ChartSpline,
    value: 'plot',
  },
  {
    label: 'Code',
    icon: CodeXml,
    value: 'code',
  },
  {
    label: 'Logs',
    icon: Scroll,
    value: 'logs',
  },
]

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
