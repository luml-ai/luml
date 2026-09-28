<script lang="ts">
import type { AssetKind } from '../../model/types'

export interface CellTab {
  id: string
  label: string
  /** Output tabs carry their asset kind for the icon. */
  kind?: AssetKind
  /** Implicit tabs: code, logs, and the live console while running. */
  icon?: 'code' | 'logs' | 'console'
  live?: boolean
}

const TABLIST_PT = {
  root: { class: 'bg-transparent!' },
  tabList: { class: 'bg-transparent!' },
}
</script>

<script setup lang="ts">
import { Tab, TabList, Tabs } from 'primevue'
import { Code2, ScrollText, SquareTerminal, type LucideIcon } from 'lucide-vue-next'
import { KIND_ICONS } from '../../ui/kinds'

/** One tab idiom for the app: the same `Tabs` the flow's own views use. */
defineProps<{ tabs: CellTab[]; selected: string }>()

const emit = defineEmits<{ select: [id: string] }>()

const IMPLICIT_ICONS: Record<'code' | 'logs' | 'console', LucideIcon> = {
  code: Code2,
  logs: ScrollText,
  console: SquareTerminal,
}

function iconFor(tab: CellTab): LucideIcon {
  if (tab.kind) return KIND_ICONS[tab.kind] ?? KIND_ICONS.unknown
  return IMPLICIT_ICONS[tab.icon ?? 'code']
}
</script>

<template>
  <Tabs :value="selected" scrollable class="bg-transparent!">
    <TabList :pt="TABLIST_PT">
      <Tab
        v-for="tab in tabs"
        :key="tab.id"
        :value="tab.id"
        class="tab"
        @click="emit('select', tab.id)"
      >
        <component :is="iconFor(tab)" :size="14" class="shrink-0" />
        <span class="font-mono">{{ tab.label }}</span>
        <span
          v-if="tab.live"
          class="h-1.5 w-1.5 animate-pulse rounded-full bg-(--p-message-info-color)"
        />
      </Tab>
    </TabList>
  </Tabs>
</template>

<style scoped>
.tab {
  display: flex;
  align-items: center;
  gap: 6px;
  border: none;
  padding: 0.375rem 0.625rem;
  /* The compact-control size the reference uses for its own toolbars — never
     below it. A tab strip is chrome, but it is chrome the reader aims at. */
  font-size: 0.875rem;
  background: transparent !important;
  white-space: nowrap;
}
</style>
