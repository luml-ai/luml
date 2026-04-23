<script setup lang="ts">
import { ref } from 'vue'
import { InputText, Button } from 'primevue'
import { FolderOpen, ArrowUp, Folder, Github, Check } from 'lucide-vue-next'
import { api } from '@/lib/api'
import type { BrowseEntry } from '@/lib/api/prisma/prisma.interfaces'

const model = defineModel<string>({ default: '' })

const open = ref(false)
const loading = ref(false)
const current = ref('')
const parent = ref<string | null>(null)
const dirs = ref<BrowseEntry[]>([])
const isGit = ref(false)
const error = ref('')

async function browse(path?: string) {
  error.value = ''
  loading.value = true
  try {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 5000)
    const result = await api.dataAgent.browsePath(path, { signal: controller.signal })
    clearTimeout(timeout)
    current.value = result.current
    parent.value = result.parent
    dirs.value = result.dirs
    isGit.value = result.is_git
  } catch (e: any) {
    if (e?.code === 'ERR_CANCELED' || e?.name === 'AbortError') {
      error.value = 'Request timed out — is the agent server running?'
    } else {
      error.value = e?.response?.data?.detail ?? 'Failed to browse'
    }
  } finally {
    loading.value = false
  }
}

function toggle() {
  if (open.value) {
    open.value = false
    return
  }
  open.value = true
  browse(model.value || undefined)
}

function selectDir(path: string) {
  model.value = path
  open.value = false
}

async function navigateTo(path: string) {
  await browse(path)
}
</script>

<template>
  <div class="folder-picker">
    <div class="input-row">
      <InputText :model-value="model" readonly placeholder="/home/user/repo" class="path-input" />
      <Button severity="secondary" size="small" class="browse-btn" @click="toggle">
        <FolderOpen :size="14" />
      </Button>
    </div>
    <div v-if="open" class="browse-panel">
      <div class="browse-header">
        <span class="browse-path">{{ current || 'Loading...' }}</span>
        <Button
          v-if="isGit"
          size="small"
          @click="selectDir(current)"
        >
          <Check :size="14" />
          <span>Select this</span>
        </Button>
      </div>
      <div class="browse-list">
        <div v-if="loading" class="browse-empty">Loading...</div>
        <template v-else>
          <div v-if="parent != null" class="browse-item browse-item--parent" @click="navigateTo(parent)">
            <ArrowUp :size="14" />
            <span>..</span>
          </div>
          <div v-for="dir in dirs" :key="dir.path" class="browse-item" @click="navigateTo(dir.path)">
            <component :is="dir.is_git ? Github : Folder" :size="14" />
            <span class="dir-name">{{ dir.name }}</span>
            <Button
              v-if="dir.is_git"
              size="small"
              class="select-btn"
              @click.stop="selectDir(dir.path)"
            >
              <span>Select</span>
            </Button>
          </div>
          <div v-if="dirs.length === 0" class="browse-empty">No subdirectories</div>
        </template>
      </div>
      <div v-if="error" class="browse-error">{{ error }}</div>
    </div>
  </div>
</template>

<style scoped>
.folder-picker {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.input-row {
  display: flex;
  gap: 8px;
}

.path-input {
  flex: 1;
}

.browse-btn {
  width: 2.25rem !important;
  height: 2.25rem !important;
  flex-shrink: 0;
}

.browse-panel {
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  overflow: hidden;
}

.browse-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--p-content-background);
  border-bottom: 1px solid var(--p-content-border-color);
  gap: 8px;
}

.browse-path {
  font-size: 13px;
  color: var(--p-text-muted-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.browse-list {
  max-height: 250px;
  overflow-y: auto;
}

.browse-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.15s;
}

.browse-item:hover {
  background: var(--p-content-hover-background);
}

.browse-item--parent {
  color: var(--p-text-muted-color);
}

.dir-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.select-btn {
  flex-shrink: 0;
}

.browse-empty {
  padding: 16px;
  text-align: center;
  color: var(--p-text-muted-color);
  font-size: 14px;
}

.browse-error {
  padding: 8px 12px;
  color: var(--p-red-500);
  font-size: 13px;
}
</style>
