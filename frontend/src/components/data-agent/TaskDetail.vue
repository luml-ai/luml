<script setup lang="ts">
import { ref } from 'vue'
import { Button, Tag } from 'primevue'
import { Play, Check, Trash2 } from 'lucide-vue-next'
import type { AgentTask } from '@/lib/api/data-agent/data-agent.interfaces'
import { api } from '@/lib/api'
import { statusSeverity } from './board/board.types'
import MergeDialog from './MergeDialog.vue'

const props = defineProps<{
  task: AgentTask
}>()

const emit = defineEmits<{
  refresh: []
}>()

const showMerge = ref(false)

async function handleDelete() {
  await api.dataAgent.deleteTask(props.task.id)
  emit('refresh')
}

async function handleResume() {
  await api.dataAgent.openTerminal(props.task.id)
  emit('refresh')
}
</script>

<template>
  <div class="task-detail">
    <div class="header">
      <h3 class="task-title">{{ task.name }}</h3>
      <Tag :value="task.status" :severity="statusSeverity(task.status)" />
    </div>
    <div class="info">
      <div><strong>Branch:</strong> {{ task.branch }}</div>
      <div><strong>Agent:</strong> {{ task.agent_id }}</div>
      <div><strong>Worktree:</strong> {{ task.worktree_path }}</div>
      <div v-if="task.prompt"><strong>Prompt:</strong> {{ task.prompt }}</div>
      <div><strong>Created:</strong> {{ task.created_at }}</div>
    </div>
    <div class="actions">
      <Button
        v-if="!task.is_alive && task.worktree_path"
        severity="info"
        @click="handleResume"
      >
        <Play :size="14" />
        <span>Resume</span>
      </Button>
      <Button
        v-if="task.status === 'succeeded'"
        severity="success"
        @click="showMerge = true"
      >
        <Check :size="14" />
        <span>Merge</span>
      </Button>
      <Button
        severity="warn"
        variant="outlined"
        @click="handleDelete"
      >
        <Trash2 :size="14" />
        <span>Delete</span>
      </Button>
    </div>
    <MergeDialog
      :visible="showMerge"
      :task="task"
      @close="showMerge = false"
      @merged="showMerge = false; emit('refresh')"
    />
  </div>
</template>

<style scoped>
.task-detail {
  padding: 16px 20px;
  border-bottom: 1px solid var(--p-content-border-color);
  background: var(--p-card-background);
}

.header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.task-title {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
  color: var(--p-text-color);
}

.info {
  font-size: 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
  color: var(--p-text-muted-color);
}

.actions {
  display: flex;
  gap: 8px;
}
</style>
