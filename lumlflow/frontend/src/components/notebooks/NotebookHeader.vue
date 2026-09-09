<template>
  <div class="toolbar">
    <div class="toolbar-left">
      <RouterLink :to="backTarget" class="toolbar-back-button">
        <ChevronLeft :size="14" />
      </RouterLink>
      <div class="toolbar-title">
        <span class="status-circle"></span>
        <span>{{ flowName }}</span>
        <span>/</span>
        <span>{{ branchName }}</span>
      </div>
      <Tag value="Unpaired" severity="secondary" />
      <button class="toolbar-pair-button">Pair an agent</button>
    </div>
    <div class="toolbar-right">
      <SelectButton
        :model-value="flowStore.viewMode"
        :options="options"
        :allow-empty="false"
        optionLabel="label"
        optionValue="value"
        aria-labelledby="basic"
        size="small"
        @update:model-value="flowStore.setViewMode($event)"
      />
      <Button variant="outlined" severity="secondary" size="small" class="toolbar-settings-button">
        <template #icon> <Bolt :size="12" /> </template>
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Bolt, ChevronLeft, Notebook, Workflow } from 'lucide-vue-next'
import { Button, SelectButton, Tag } from 'primevue'
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { ROUTE_NAMES } from '@/router/router.const'
import { useFlowStore } from '@/store/flow'

const flowStore = useFlowStore()

const backTarget = computed(() => {
  const flow = flowStore.currentFlow?.replace(/\/+$/, '')
  const lastSlash = flow?.lastIndexOf('/') ?? -1
  const directory = lastSlash > 0 ? flow?.slice(0, lastSlash) : undefined

  return {
    name: ROUTE_NAMES.WORKSPACES,
    query: directory ? { directory } : {},
  }
})

const flowName = computed(() => {
  const flow = flowStore.currentFlow?.replace(/\/+$/, '')
  if (!flow) return ''
  const lastSlash = flow.lastIndexOf('/')
  return lastSlash >= 0 ? flow.slice(lastSlash + 1) : flow
})

const branchName = computed(() => flowStore.currentBranch?.branch ?? '')

const options = [
  {
    label: 'Canvas',
    value: 'canvas',
    icon: Workflow,
  },
  {
    label: 'Notebook',
    value: 'notebook',
    icon: Notebook,
  },
]
</script>

<style scoped>
@reference "@/assets/css/index.css";

.toolbar {
  @apply flex items-center justify-between gap-5 py-2.5 px-5 bg-(--p-card-background) border border-surface rounded-lg;
}
.toolbar-left {
  @apply flex items-center gap-4;
}
.toolbar-back-button {
  @apply cursor-pointer shrink-0 hover:text-primary-600 transition-colors;
}
.status-circle {
  @apply w-5 h-5 shrink-0 rounded-full bg-(--p-toast-success-background) border border-(--p-toast-success-border-color) flex items-center justify-center;
}
.status-circle::before {
  @apply content-[''] w-3 h-3 rounded-full bg-(--p-badge-success-background) shadow-[0px_2px_8px_0px_#22C55E80];
}
.toolbar-title {
  @apply flex items-center gap-2;
}
.toolbar-pair-button {
  @apply text-primary cursor-pointer hover:text-primary-600 transition-colors;
}
.toolbar-right {
  @apply flex gap-4;
}
.toolbar-settings-button {
  @apply p-0 h-10! w-10!;
}
</style>
