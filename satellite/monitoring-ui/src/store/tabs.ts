import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { TabKey } from '@/types/tabs'
import { LLM_TABS, ML_TABS } from '@/constants/tabs'
import { useHeaderStore } from '@/store/header'

export const useTabsStore = defineStore('tabs', () => {
  const headerStore = useHeaderStore()

  const selectedTab = ref<TabKey>(TabKey.OVERVIEW)

  const tabs = computed(() => (headerStore.modelKind === 'tabular' ? ML_TABS : LLM_TABS))

  const activeTab = computed(() =>
    tabs.value.some((tab) => tab.key === selectedTab.value) ? selectedTab.value : TabKey.OVERVIEW,
  )

  function setActiveTab(key: TabKey) {
    selectedTab.value = key
  }

  return {
    selectedTab,
    tabs,
    activeTab,
    setActiveTab,
  }
})
