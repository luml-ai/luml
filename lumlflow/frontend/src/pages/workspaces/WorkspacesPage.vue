<template>
  <div>
    <div class="mb-6">
      <div class="flex items-center justify-between gap-4 mb-1">
        <div class="flex items-center">
          <span>Notebooks</span>
          <UiPreviewBadge />
        </div>
        <OpenFlowsSummary />
      </div>
      <WorkspacePath />
    </div>
    <WorkspaceFolder :items="workspaceStore.sortedItems" class="mb-4" />
    <CreateNewFlow v-if="!workspaceStore.isDirectoryLoading" :existing-names="existingFlowNames" />
  </div>
</template>

<script setup lang="ts">
import UiPreviewBadge from '@/components/ui/UiPreviewBadge.vue'
import { useToast } from 'primevue'
import { useIntervalFn } from '@vueuse/core'
import { computed, onBeforeMount } from 'vue'
import { useRoute } from 'vue-router'
import { OPEN_FLOWS_REFRESH_MS, useWorkspaceStore } from '@/store/workspace'
import { errorToast } from '@/toasts'
import WorkspaceFolder from '@/components/workspace/folder/WorkspaceFolder.vue'
import CreateNewFlow from '@/components/workspace/CreateNewFlow.vue'
import OpenFlowsSummary from '@/components/workspace/OpenFlowsSummary.vue'
import WorkspacePath from '@/components/workspace/WorkspacePath.vue'

const route = useRoute()
const toast = useToast()
const workspaceStore = useWorkspaceStore()

const existingFlowNames = computed(() =>
  workspaceStore.sortedItems.filter((item) => item.type === 'flow').map((item) => item.name),
)

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
