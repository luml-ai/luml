<script setup lang="ts">
import { computed } from 'vue'
import { Tag, Button } from 'primevue'
import { Waypoints, ListTodo, Play, Trash2 } from 'lucide-vue-next'
import { type BoardItem, statusSeverity } from './board.types'

const props = defineProps<{
  item: BoardItem
  repositoryName: string
}>()

const emit = defineEmits<{
  select: []
  start: []
  delete: []
}>()

const name = computed(() => props.item.data.name)
const isTask = computed(() => props.item.kind === 'task')
const waitingInput = computed(() => !!props.item.data.has_waiting_input)

const displayStatus = computed(() =>
  waitingInput.value ? 'waiting for input' : props.item.data.status,
)
const severityValue = computed(() =>
  waitingInput.value ? 'warn' : statusSeverity(props.item.data.status),
)

const relativeTime = computed(() => {
  const ms = Date.now() - new Date(props.item.data.updated_at).getTime()
  const seconds = Math.floor(ms / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
})

const showStart = computed(() => props.item.data.status === 'pending')
</script>

<template>
  <div class="board-card" @click="emit('select')">
    <div class="card-top">
      <component :is="isTask ? ListTodo : Waypoints" :size="14" class="type-icon" />
      <span class="card-name">{{ name }}</span>
    </div>
    <div class="card-meta">
      <span class="repo-name">{{ repositoryName }}</span>
      <Tag :value="displayStatus" :severity="severityValue" class="status-tag" />
    </div>
    <div class="card-footer">
      <span class="time">{{ relativeTime }}</span>
      <div class="quick-actions" @click.stop>
        <Button
          v-if="showStart"
          variant="text"
          severity="success"
          class="action-btn"
          v-tooltip.top="'Start'"
          @click="emit('start')"
        >
          <template #icon><Play :size="14" /></template>
        </Button>
<Button
          variant="text"
          severity="secondary"
          class="action-btn"
          v-tooltip.top="'Delete'"
          @click="emit('delete')"
        >
          <template #icon><Trash2 :size="14" /></template>
        </Button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.board-card {
  padding: 10px 12px;
  border: 1px solid var(--p-content-border-color);
  border-radius: 6px;
  background: var(--p-card-background);
  cursor: pointer;
  transition: box-shadow 0.15s;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.board-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.card-top {
  display: flex;
  align-items: center;
  gap: 6px;
}

.type-icon {
  color: var(--p-text-muted-color);
  flex-shrink: 0;
}

.card-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--p-text-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 6px;
}

.repo-name {
  font-size: 11px;
  color: var(--p-text-muted-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.status-tag {
  font-size: 10px;
  flex-shrink: 0;
}

.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.time {
  font-size: 11px;
  color: var(--p-text-muted-color);
}

.quick-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.15s;
}

.board-card:hover .quick-actions {
  opacity: 1;
}

.action-btn {
  width: 32px !important;
  height: 32px !important;
}
</style>
