<script setup lang="ts">
import { Select } from 'primevue'
import type { AgentRepository } from '@/lib/api/data-agent/data-agent.interfaces'

defineProps<{
  repositories: AgentRepository[]
  repositoryFilter: string | null
}>()

const emit = defineEmits<{
  'update:repositoryFilter': [value: string | null]
}>()
</script>

<template>
  <div class="board-toolbar">
    <Select
      :model-value="repositoryFilter"
      :options="[{ id: null, name: 'All repositories' }, ...repositories]"
      option-label="name"
      option-value="id"
      placeholder="All repositories"
      size="small"
      class="repo-filter"
      @update:model-value="emit('update:repositoryFilter', $event)"
    />
  </div>
</template>

<style scoped>
.board-toolbar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  flex-shrink: 0;
}

.repo-filter {
  width: 200px;
}
</style>
