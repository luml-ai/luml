<template>
  <Tabs :value="modelValue" @update:value="updateValue">
    <TabList ref="tabListRef" :pt="tabListPt">
      <Tab v-for="tab in tabs" :key="tab.id" :value="tab.id" class="tab">
        <component :is="tab.icon" :size="14" />
        <span>{{ tab.label }}</span>
      </Tab>
      <span class="p-tablist-active-bar ink-bar" :style="inkBarStyle" />
    </TabList>
  </Tabs>
</template>

<script setup lang="ts">
import type { NotebookCellTabsProps } from '@/components/notebooks/cell/cell.interface'
import { computed, ref } from 'vue'
import { useMutationObserver, useResizeObserver } from '@vueuse/core'
import { Tabs, TabList, Tab } from 'primevue'
import { CELL_TABS_LIST_PT } from '@/components/notebooks/cell/cell.const'

defineProps<NotebookCellTabsProps>()

const modelValue = defineModel<string>('modelValue', { required: true })

function updateValue(value: string | number) {
  modelValue.value = String(value)
}

const tabListPt = {
  ...CELL_TABS_LIST_PT,
  activeBar: { style: { display: 'none' } },
}

const tabListRef = ref<{ $el: HTMLElement } | null>(null)
const tabListContainer = computed(
  () => tabListRef.value?.$el.querySelector<HTMLElement>('.p-tablist-tab-list') ?? null,
)

const indicatorLeft = ref(0)
const indicatorWidth = ref(0)
const inkBarStyle = computed(() => ({
  transform: `translateX(${indicatorLeft.value}px)`,
  width: `${indicatorWidth.value}px`,
}))

function updateIndicator() {
  const activeTab = tabListContainer.value?.querySelector<HTMLElement>(
    '[data-pc-name="tab"][data-p-active="true"]',
  )
  if (!activeTab) return
  indicatorLeft.value = activeTab.offsetLeft
  indicatorWidth.value = activeTab.offsetWidth
}

useResizeObserver(tabListContainer, updateIndicator)
useMutationObserver(tabListContainer, updateIndicator, {
  attributes: true,
  attributeFilter: ['data-p-active'],
  subtree: true,
})
</script>

<style scoped>
@reference "@/assets/css/index.css";

.tab {
  @apply border-none flex items-center gap-1.5 px-2 py-1;
}

.ink-bar {
  left: 0;
  pointer-events: none;
  will-change: transform, width;
}
</style>
