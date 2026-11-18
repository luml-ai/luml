<template>
  <LumlflowCard>
    <div v-if="loading">
      <Skeleton v-for="i in 4" :key="i" height="40px" class="skeleton" />
    </div>
    <div v-else-if="items.length === 0">
      <p class="empty">This directory is empty</p>
    </div>
    <template v-else>
      <WorkspaceFolderItem
        v-for="item in items"
        :key="item.id"
        :item="item"
        :open-flows="openFlows"
        :menu-open="item.id === menuOpenId"
        :renaming="item.id === renamingId"
        :rename-value="renameValue"
        :selected="item.id === selectedId"
      />
    </template>
  </LumlflowCard>
</template>

<script setup lang="ts">
import { Skeleton } from '@/ui'
import LumlflowCard from '@/ui/LumlflowCard.vue'
import type { OpenFlow } from '@/components/FlowStateMarker/openFlows'
import type { WorkspaceFolderItem as Item } from '@/blocks/WorkspaceFolder/interface'
import WorkspaceFolderItem from './WorkspaceFolderItem.vue'

type Props = {
  items: Item[]
  openFlows?: OpenFlow[]
  loading?: boolean
  menuOpenId?: string | null
  renamingId?: string | null
  renameValue?: string
  /** UIP-002: the file row whose preview is open. */
  selectedId?: string | null
}

withDefaults(defineProps<Props>(), {
  openFlows: () => [],
  loading: false,
  menuOpenId: null,
  renamingId: null,
  renameValue: '',
  selectedId: null,
})
</script>

<style scoped>
.skeleton:not(:last-child) {
  margin-bottom: 0.25rem;
}

.empty {
  font-size: 0.875rem;
  line-height: 1.25rem;
}
</style>
