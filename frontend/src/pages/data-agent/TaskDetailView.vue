<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button } from 'primevue'
import { ArrowLeft } from 'lucide-vue-next'
import { api } from '@/lib/api'
import type { AgentTask } from '@/lib/api/data-agent/data-agent.interfaces'
import TaskDetail from '@/components/data-agent/TaskDetail.vue'
import TerminalTabs from '@/components/data-agent/TerminalTabs.vue'

const route = useRoute()
const router = useRouter()

const task = ref<AgentTask | null>(null)
const idleSessions = ref<string[]>([])

const taskId = computed(() => String(route.params.taskId || ''))
const activeTasks = computed(() => {
  if (!task.value?.session_id || !task.value.is_alive) return []
  return [task.value]
})

let refreshInterval: ReturnType<typeof setInterval> | null = null

async function refresh() {
  try {
    task.value = await api.dataAgent.getTask(taskId.value)
  } catch {
    task.value = null
  }
}

function goBack() {
  router.push({ name: 'data-agent-board' })
}

onMounted(() => {
  refresh()
  refreshInterval = setInterval(refresh, 5000)
})

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval)
})
</script>

<template>
  <div class="task-detail-view">
    <div class="detail-header">
      <Button variant="text" severity="secondary" @click="goBack">
        <template #icon><ArrowLeft :size="16" /></template>
      </Button>
      <span class="detail-title">Task Detail</span>
    </div>
    <div v-if="task" class="detail-content">
      <TaskDetail :task="task" @refresh="refresh" />
      <TerminalTabs
        :tasks="activeTasks"
        @update:idle-sessions="idleSessions = $event"
      />
    </div>
    <div v-else class="empty">Loading...</div>
  </div>
</template>

<style scoped>
.task-detail-view {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 0;
  flex-shrink: 0;
}

.detail-title {
  font-size: 16px;
  font-weight: 500;
  color: var(--p-text-color);
}

.detail-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  background: var(--p-card-background);
}

.empty {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  color: var(--p-text-muted-color);
  font-size: 14px;
}
</style>
