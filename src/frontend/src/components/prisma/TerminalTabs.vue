<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { Tabs, TabList, Tab, TabPanels, TabPanel } from 'primevue'
import type { AgentTask } from '@/lib/api/prisma/prisma.interfaces'
import TerminalPanel from './TerminalPanel.vue'

const props = defineProps<{
  tasks: AgentTask[]
}>()

const emit = defineEmits<{
  'update:idleSessions': [sessions: string[]]
}>()

const activeTab = ref<string>('')
const idleSessions = reactive(new Set<string>())

function onIdleChange(sessionId: string, idle: boolean) {
  if (idle) {
    idleSessions.add(sessionId)
  } else {
    idleSessions.delete(sessionId)
  }
  emit('update:idleSessions', [...idleSessions])
}

watch(
  () => props.tasks,
  (tasks) => {
    if (tasks.length > 0 && !tasks.some((t) => t.session_id === activeTab.value)) {
      activeTab.value = tasks[0].session_id ?? ''
    }
  },
  { immediate: true },
)
</script>

<template>
  <div v-if="tasks.length > 0" class="terminal-tabs">
    <Tabs v-model:value="activeTab">
      <TabList>
        <Tab v-for="task in tasks" :key="task.session_id" :value="task.session_id ?? ''">
          {{ task.name }}
        </Tab>
      </TabList>
      <TabPanels>
        <TabPanel v-for="task in tasks" :key="task.session_id" :value="task.session_id ?? ''">
          <TerminalPanel
            v-if="task.session_id"
            :session-id="task.session_id"
            :active="activeTab === task.session_id"
            :task-name="task.name"
            @idle-change="(idle: boolean) => onIdleChange(task.session_id!, idle)"
          />
        </TabPanel>
      </TabPanels>
    </Tabs>
  </div>
  <div v-else class="no-terminals">
    <p>No active terminals</p>
  </div>
</template>

<style scoped>
.terminal-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--p-surface-900);
  border-radius: 0 0 8px 0;
}

.terminal-tabs :deep(.p-tabs) {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.terminal-tabs :deep(.p-tabpanels) {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0;
}

.terminal-tabs :deep(.p-tabpanel) {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0;
}

.no-terminals {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--p-text-muted-color);
  font-size: 14px;
}
</style>
