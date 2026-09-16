import type { CellSummary, PreviewBlock } from '@/api/slices/workspace/workspace.interface'
import type { CellTab } from '@/components/notebooks/cell/cell.interface'
import { CodeXml, Scroll } from 'lucide-vue-next'
import { computed, ref, toValue, watch, type MaybeRefOrGetter } from 'vue'
import { useFlowStore } from '@/store/flow'
import { capitalize } from '@/helpers/string'
import {
  CELL_OUTPUT_KIND_ICONS,
  DEFAULT_OUTPUT_KIND_ICON,
} from '@/components/notebooks/cell/cell.const'

export const CODE_TAB_ID = 'code'
export const LOGS_TAB_ID = 'logs'
const OUTPUT_TAB_PREFIX = 'output:'

export type CellTabContent =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; blocks: PreviewBlock[]; truncated: boolean }

function outputTabId(name: string): string {
  return `${OUTPUT_TAB_PREFIX}${name}`
}

function outputNameFromTabId(id: string): string {
  return id.slice(OUTPUT_TAB_PREFIX.length)
}

export function useCellTabs(cell: MaybeRefOrGetter<CellSummary>) {
  const flowStore = useFlowStore()

  const tabs = computed<CellTab[]>(() => {
    const summary = toValue(cell)
    const outputs = Object.entries(summary.kinds).map(([name, kind]) => ({
      id: outputTabId(name),
      label: capitalize(name),
      icon: CELL_OUTPUT_KIND_ICONS[kind] ?? DEFAULT_OUTPUT_KIND_ICON,
    }))
    return [
      ...outputs,
      { id: CODE_TAB_ID, label: 'Code', icon: CodeXml },
      { id: LOGS_TAB_ID, label: 'Logs', icon: Scroll },
    ]
  })

  const activeTab = ref<string>(tabs.value[0]?.id ?? CODE_TAB_ID)

  const cache = new Map<string, CellTabContent>()
  const content = ref<CellTabContent>({ status: 'idle' })

  async function loadOutput(tabId: string) {
    const cached = cache.get(tabId)
    if (cached) {
      content.value = cached
      return
    }
    content.value = { status: 'loading' }
    try {
      const asset = await flowStore.fetchAssetPreview(
        toValue(cell).slug,
        outputNameFromTabId(tabId),
      )
      const loaded: CellTabContent = asset.preview
        ? { status: 'ready', blocks: asset.preview.blocks, truncated: asset.preview.truncated }
        : { status: 'error', message: 'This output has not produced a value yet' }
      cache.set(tabId, loaded)
      content.value = loaded
    } catch (error) {
      content.value = {
        status: 'error',
        message: error instanceof Error ? error.message : 'Failed to load preview',
      }
    }
  }

  watch(tabs, (list) => {
    if (!list.some((tab) => tab.id === activeTab.value)) {
      activeTab.value = list[0]?.id ?? CODE_TAB_ID
    }
  })

  watch(
    activeTab,
    (tabId) => {
      if (tabId === CODE_TAB_ID || tabId === LOGS_TAB_ID) {
        content.value = { status: 'idle' }
        return
      }
      void loadOutput(tabId)
    },
    { immediate: true },
  )

  watch(
    () => toValue(cell).state,
    () => {
      cache.clear()
      if (activeTab.value !== CODE_TAB_ID && activeTab.value !== LOGS_TAB_ID) {
        void loadOutput(activeTab.value)
      }
    },
  )

  return { tabs, activeTab, content }
}
