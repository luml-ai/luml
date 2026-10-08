<template>
  <div>
    <div class="mb-6">
      <button
        class="inline-flex gap-0.5 items-center mb-1 cursor-pointer hover:text-primary transition-colors"
        @click="goUp"
      >
        <ChevronLeft :size="14" />
        <span>Notebooks</span>
      </button>
      <div class="flex items-center justify-between gap-4 pl-4">
        <div class="text-(--p-breadcrumb-item-color) truncate">
          {{ workspaceStore.currentDirectory }}
        </div>
        <span v-if="openSummary" class="shrink-0 text-sm text-muted-color">{{ openSummary }}</span>
      </div>
    </div>
    <WorkspaceFolder :items="workspaceStore.sortedItems" class="mb-4" />
    <CreateNewFlow v-if="!workspaceStore.isDirectoryLoading" :existing-names="existingFlowNames" />
    <section v-for="group in elsewhereGroups" :key="group.directory" class="mt-6">
      <div class="text-(--p-breadcrumb-item-color) truncate pl-4 mb-2">{{ group.directory }}</div>
      <Card>
        <template #content>
          <WorkspaceFolderItemFlow
            v-for="item in group.items"
            :key="item.id"
            :item="item"
            :actions="false"
          />
        </template>
      </Card>
    </section>
  </div>
</template>

<script setup lang="ts">
import type { IWorkspaceFolderItem } from '@/components/workspace/folder/interface'
import { ChevronLeft } from 'lucide-vue-next'
import { Card, useToast } from 'primevue'
import { useIntervalFn } from '@vueuse/core'
import { computed, onBeforeMount } from 'vue'
import { useRoute } from 'vue-router'
import { OPEN_FLOWS_REFRESH_MS, useWorkspaceStore } from '@/store/workspace'
import { errorToast } from '@/toasts'
import { baseName, parentDirectory } from '@/helpers/path'
import WorkspaceFolder from '@/components/workspace/folder/WorkspaceFolder.vue'
import WorkspaceFolderItemFlow from '@/components/workspace/folder/WorkspaceFolderItemFlow.vue'
import CreateNewFlow from '@/components/workspace/CreateNewFlow.vue'

const route = useRoute()
const toast = useToast()
const workspaceStore = useWorkspaceStore()

const existingFlowNames = computed(() =>
  workspaceStore.sortedItems.filter((item) => item.type === 'flow').map((item) => item.name),
)

const openSummary = computed(() => {
  const totals = workspaceStore.openFlowsTotals
  if (totals.open_flows === 0) return null
  const open = `${totals.open_flows} open`
  return totals.running_kernels ? `${open} · ${totals.running_kernels} running` : open
})

const elsewhereGroups = computed(() => {
  const groups = new Map<string, IWorkspaceFolderItem[]>()
  for (const flow of workspaceStore.openFlowsElsewhere) {
    const directory = parentDirectory(flow.path) ?? flow.path
    const items = groups.get(directory) ?? []
    items.push({ id: flow.path, name: baseName(flow.path), type: 'flow', path: flow.path, size: 0 })
    groups.set(directory, items)
  }
  return [...groups].map(([directory, items]) => ({ directory, items }))
})

async function goUp() {
  try {
    await workspaceStore.navigateUp()
  } catch (error) {
    toast.add(errorToast(error))
  }
}

// useIntervalFn clears itself when the page unmounts.
useIntervalFn(() => workspaceStore.fetchOpenFlows(), OPEN_FLOWS_REFRESH_MS)

onBeforeMount(async () => {
  try {
    const directory = typeof route.query.directory === 'string' ? route.query.directory : undefined
    await workspaceStore.fetchDirectory(directory)
  } catch (error) {
    toast.add(errorToast(error))
  }
})
</script>

<style scoped></style>
