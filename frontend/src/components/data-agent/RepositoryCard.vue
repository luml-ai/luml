<script setup lang="ts">
import { Button } from 'primevue'
import { FolderGit, Trash2, Plus } from 'lucide-vue-next'
import type { AgentRepository } from '@/lib/api/data-agent/data-agent.interfaces'

type Props = {
  type: 'default' | 'create'
  data?: AgentRepository
}

defineProps<Props>()

const emit = defineEmits<{
  createNew: []
  delete: [id: string, name: string]
}>()

function truncateMiddle(str: string, maxLen: number = 40): string {
  if (str.length <= maxLen) return str
  const keep = Math.floor((maxLen - 3) / 2)
  return str.slice(0, keep) + '...' + str.slice(-keep)
}

function onDelete(repo: AgentRepository) {
  emit('delete', repo.id, repo.name)
}
</script>

<template>
  <article class="card">
    <div v-if="type === 'default' && data" class="content">
      <div class="header">
        <h3 class="title">
          <FolderGit :size="20" color="var(--p-primary-color)" class="icon" />
          <span>{{ data.name }}</span>
        </h3>
        <Button variant="text" severity="secondary" class="delete-btn" @click="onDelete(data)">
          <template #icon>
            <Trash2 :size="14" />
          </template>
        </Button>
      </div>
      <p class="path" :title="data.path">{{ truncateMiddle(data.path, 60) }}</p>
    </div>

    <div v-if="type === 'create'" class="content content--center">
      <Button severity="secondary" rounded @click="$emit('createNew')">
        <template #icon>
          <Plus :size="14" />
        </template>
      </Button>
      <h3 class="title">Add new repository</h3>
      <p class="text">Connect a git repository to start running agents</p>
    </div>
  </article>
</template>

<style scoped>
.card {
  padding: 16px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  box-shadow: var(--card-shadow);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.content--center {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 8px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.title {
  font-size: 16px;
  font-weight: 500;
  display: flex;
  gap: 6px;
  align-items: center;
  margin: 0;
}

.icon {
  flex: 0 0 auto;
}

.delete-btn {
  width: 28px !important;
  height: 28px !important;
}

.path {
  font-size: 12px;
  color: var(--p-text-muted-color);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.text {
  font-size: 12px;
  color: var(--p-text-muted-color);
  margin: 0;
}
</style>
