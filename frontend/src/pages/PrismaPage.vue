<script setup lang="ts">
import { ref, computed, provide, watch, onMounted } from 'vue'
import { useRoute, useRouter, RouterView } from 'vue-router'
import { Tabs, TabList, Tab, TabPanels, TabPanel, Button, Dialog, Tag } from 'primevue'
import { KanbanSquare, FolderGit, Plus, Monitor, Terminal } from 'lucide-vue-next'
import type { AgentRepository } from '@/lib/api/prisma/prisma.interfaces'
import { api } from '@/lib/api'
import { usePrismaStore } from '@/stores/prisma'
import { useBackendStatus } from '@/hooks/useBackendStatus'

import BackendOffline from '@/components/prisma/BackendOffline.vue'
import BackendIndicator from '@/components/prisma/BackendIndicator.vue'
import NewRepositoryDialog from '@/components/prisma/NewRepositoryDialog.vue'
import NewItemDialog from '@/components/prisma/NewItemDialog.vue'
import TerminalPanel from '@/components/prisma/TerminalPanel.vue'
import BoardView from '@/pages/prisma/BoardView.vue'
import RepositoriesView from '@/pages/prisma/RepositoriesView.vue'

const store = usePrismaStore()
const route = useRoute()
const router = useRouter()
const { isOffline, isLoading, versionMismatch, check } = useBackendStatus()

const repositories = ref<AgentRepository[]>([])
const showNewRepository = ref(false)
const newItemType = ref<'task' | 'workflow' | null>(null)
const showDebugSessions = ref(false)
const debugSessions = ref<any[]>([])
const terminalSessionId = ref<string | null>(null)
const terminalLabel = ref('Terminal')
const showTerminal = ref(false)

const isDetailRoute = computed(() => route.name === 'prisma-task' || route.name === 'prisma-run')

const activeTab = ref(route.name === 'prisma-repos' ? 'repositories' : 'board')

watch(
  () => route.name,
  (name) => {
    if (name === 'prisma-board') activeTab.value = 'board'
    else if (name === 'prisma-repos') activeTab.value = 'repositories'
  },
)

watch(activeTab, (tab) => {
  const target = tab === 'repositories' ? 'prisma-repos' : 'prisma-board'
  if (route.name !== target) {
    router.replace({ name: target })
  }
})

const tabsListPT = {
  tabList: { style: 'border-left: none; border-top: none; border-right: none;' },
}

const boardRefreshTrigger = ref(0)

provide('showNewRepository', showNewRepository)
provide('newItemType', newItemType)
provide('boardRefreshTrigger', boardRefreshTrigger)

async function refreshRepositories() {
  repositories.value = await api.dataAgent.listRepositories()
  store.repositories = repositories.value
}

async function openDebugSessions() {
  debugSessions.value = await api.dataAgent.getDebugSessions()
  showDebugSessions.value = true
}

function openTerminalDialog(sessionId: string, label?: string) {
  terminalSessionId.value = sessionId
  terminalLabel.value = label ?? 'Terminal'
  showTerminal.value = true
}

function closeTerminal() {
  showTerminal.value = false
  terminalSessionId.value = null
}

function openDebugTerminal(sessionId: string) {
  openTerminalDialog(sessionId, 'Debug session')
  showDebugSessions.value = false
}

function onRepositoryCreated() {
  showNewRepository.value = false
  refreshRepositories()
}

function onItemCreated() {
  newItemType.value = null
  boardRefreshTrigger.value++
}

async function onRetry() {
  const ok = await check()
  if (ok) refreshRepositories()
}

async function onBackendChanged() {
  const ok = await check()
  if (ok) refreshRepositories()
}

onMounted(async () => {
  const ok = await check()
  if (ok) refreshRepositories()
})
</script>

<template>
  <div class="prisma-page" :class="{ 'is-detail': isDetailRoute }">
    <template v-if="isLoading" />
    <template v-else-if="isOffline || versionMismatch">
      <BackendOffline :version-mismatch="versionMismatch" @retry="onRetry" />
    </template>
    <template v-else>
      <header v-if="!isDetailRoute" class="page-header">
        <div class="title-row">
          <h2 class="title">
            Prisma
            <span
              v-tooltip.bottom="'This feature is in preview and may change as we refine it.'"
              class="preview-badge"
            >
              PREVIEW
            </span>
          </h2>
          <BackendIndicator @changed="onBackendChanged" />
        </div>
        <div class="header-actions">
          <Button severity="secondary" outlined @click="openDebugSessions">
            <Monitor :size="14" />
            <span>Sessions</span>
          </Button>
          <Button @click="showNewRepository = true">
            <Plus :size="14" />
            <span>New Repository</span>
          </Button>
        </div>
      </header>

      <template v-if="isDetailRoute">
        <RouterView />
      </template>
      <template v-else>
        <Tabs v-model:value="activeTab" class="main-tabs">
          <TabList :pt="tabsListPT">
            <Tab value="board" class="tab">
              <KanbanSquare :size="14" />
              <span>Board</span>
            </Tab>
            <Tab value="repositories" class="tab">
              <FolderGit :size="14" />
              <span>Repositories</span>
            </Tab>
          </TabList>
          <TabPanels class="panels">
            <TabPanel value="board" class="panel">
              <BoardView />
            </TabPanel>
            <TabPanel value="repositories" class="panel">
              <RepositoriesView />
            </TabPanel>
          </TabPanels>
        </Tabs>
      </template>
    </template>

    <!-- Shared dialogs -->
    <NewRepositoryDialog
      :visible="showNewRepository"
      @close="showNewRepository = false"
      @created="onRepositoryCreated"
    />
    <NewItemDialog
      :visible="newItemType !== null"
      :initial-type="newItemType ?? 'workflow'"
      :repositories="repositories"
      @close="newItemType = null"
      @created="onItemCreated"
    />

    <!-- Debug sessions dialog -->
    <Dialog
      :visible="showDebugSessions"
      header="PTY Sessions"
      modal
      :style="{ width: '600px' }"
      @update:visible="!$event && (showDebugSessions = false)"
    >
      <div v-if="debugSessions.length === 0" class="sessions-empty">No active PTY sessions</div>
      <div v-else class="sessions-list">
        <div v-for="s in debugSessions" :key="s.session_id" class="session-card">
          <div class="session-header">
            <code class="session-id">{{ s.session_id.substring(0, 12) }}</code>
            <Tag :value="s.alive ? 'alive' : 'dead'" :severity="s.alive ? 'success' : 'danger'" />
            <Tag :value="s.session_type" severity="info" />
          </div>
          <div class="session-details">
            <span>PID {{ s.pid }}</span>
            <span>Task {{ s.task_id }}</span>
            <span v-if="s.exit_code != null">Exit {{ s.exit_code }}</span>
          </div>
          <div v-if="s.alive" class="session-actions">
            <Button size="small" @click="openDebugTerminal(s.session_id)">
              <Terminal :size="14" />
              <span>Attach</span>
            </Button>
          </div>
        </div>
      </div>
    </Dialog>

    <!-- Terminal dialog -->
    <Dialog
      :visible="showTerminal"
      :header="terminalLabel"
      :draggable="true"
      :modal="false"
      :style="{ width: '960px', height: '580px' }"
      :content-style="{
        padding: 0,
        display: 'flex',
        flexDirection: 'column',
        flex: 1,
        overflow: 'hidden',
      }"
      class="terminal-dialog"
      position="bottom"
      @update:visible="!$event && closeTerminal()"
    >
      <TerminalPanel
        v-if="terminalSessionId"
        :session-id="terminalSessionId"
        :active="showTerminal"
        :task-name="terminalLabel"
      />
    </Dialog>
  </div>
</template>

<style scoped>
.prisma-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 130px);
}

.prisma-page:not(.is-detail) {
  padding-top: 32px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title {
  font-weight: 500;
  font-size: 24px;
  margin: 0;
  display: flex;
  align-items: flex-start;
}

.preview-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 2px 6px;
  border-radius: 6px;
  background: transparent;
  color: var(--p-primary-color);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.05em;
  cursor: help;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.prisma-page :deep(.p-tabs) {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.tab {
  border: none;
  display: flex;
  align-items: center;
  gap: 7px;
}

.panels {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.prisma-page :deep(.p-tabpanels) {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0;
}

.panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.prisma-page :deep(.p-tabpanel) {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0;
}

/* Debug sessions dialog */
.sessions-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.session-card {
  border: 1px solid var(--p-content-border-color);
  border-radius: 6px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.session-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.session-id {
  font-size: 0.85rem;
  font-weight: 500;
  background: var(--p-content-hover-background);
  padding: 2px 8px;
  border-radius: 4px;
}

.session-details {
  display: flex;
  gap: 12px;
  font-size: 0.8rem;
  color: var(--p-text-muted-color);
}

.session-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 2px;
}

.sessions-empty {
  text-align: center;
  color: var(--p-text-muted-color);
  padding: 2rem;
  font-size: 0.85rem;
}
</style>

<!-- Unscoped: PrimeVue Dialog teleports to <body>, so scoped :deep() can't reach it -->
<style>
.terminal-dialog {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.terminal-dialog .p-dialog-content {
  background: #020617;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 0;
}
</style>
