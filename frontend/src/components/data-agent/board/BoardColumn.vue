<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Tag } from 'primevue'
import { Plus } from 'lucide-vue-next'
import draggable from 'vuedraggable'
import type { AgentRepository } from '@/lib/api/data-agent/data-agent.interfaces'
import type { BoardItem } from './board.types'
import BoardCard from './BoardCard.vue'

const props = withDefaults(defineProps<{
  title: string
  severity: 'warn' | 'info' | 'success' | 'danger'
  items: BoardItem[]
  repositories: AgentRepository[]
  showCreate?: boolean
  failCount?: number
}>(), { failCount: 0 })

const emit = defineEmits<{
  select: [item: BoardItem]
  start: [item: BoardItem]
  resume: [item: BoardItem]
  delete: [item: BoardItem]
  create: []
  reorder: [items: BoardItem[]]
}>()

const localItems = ref<BoardItem[]>([])

watch(
  () => props.items,
  (val) => { localItems.value = [...val] },
  { immediate: true },
)

function onDragEnd() {
  emit('reorder', localItems.value)
}

const repoMap = computed(() => {
  const map = new Map<string, string>()
  for (const r of props.repositories) {
    map.set(r.id, r.name)
  }
  return map
})

function repoName(item: BoardItem): string {
  return repoMap.value.get(item.data.repository_id) ?? 'Unknown'
}

function itemKey(item: BoardItem): string {
  return `${item.kind}-${item.data.id}`
}
</script>

<template>
  <div class="board-column">
    <div class="column-header">
      <span class="column-title">{{ title }}</span>
      <Tag :value="String(items.length - failCount)" :severity="severity" rounded class="count-badge" />
      <Tag v-if="failCount > 0" :value="String(failCount)" severity="danger" rounded class="count-badge" />
    </div>
    <div class="column-scroll">
      <div v-if="showCreate" class="create-card" @click="emit('create')">
        <Plus :size="14" />
        <span>New task</span>
      </div>
      <draggable
        v-model="localItems"
        :item-key="itemKey"
        :animation="150"
        ghost-class="drag-ghost"
        class="drag-list"
        @end="onDragEnd"
      >
        <template #item="{ element }">
          <BoardCard
            :item="element"
            :repository-name="repoName(element)"
            @select="emit('select', element)"
            @start="emit('start', element)"
            @resume="emit('resume', element)"
            @delete="emit('delete', element)"
          />
        </template>
      </draggable>
      <div v-if="items.length === 0 && !showCreate" class="empty">No items</div>
    </div>
  </div>
</template>

<style scoped>
.board-column {
  flex: 1;
  min-width: 220px;
  display: flex;
  flex-direction: column;
  background: var(--p-content-background);
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  overflow: hidden;
}

.column-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--p-content-border-color);
  background: var(--p-card-background);
  flex-shrink: 0;
}

.column-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--p-text-color);
}

.count-badge {
  font-size: 11px;
  min-width: 20px;
  height: 20px;
}

.column-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.create-card {
  padding: 8px 12px;
  border-radius: 6px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--p-text-muted-color);
  transition: background 0.15s, color 0.15s;
}

.create-card:hover {
  background: var(--p-content-hover-background);
  color: var(--p-primary-color);
}

.empty {
  text-align: center;
  color: var(--p-text-muted-color);
  font-size: 12px;
  padding: 16px 0;
}

.drag-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.drag-ghost {
  opacity: 0.4;
}
</style>
