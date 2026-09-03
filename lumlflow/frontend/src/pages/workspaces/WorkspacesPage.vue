<template>
  <div>
    <div class="mb-6">
      <RouterLink :to="{ name: ROUTE_NAMES.HOME }" class="inline-flex gap-0.5 items-center mb-1">
        <ChevronLeft :size="14" />
        <span>Workspace</span>
      </RouterLink>
      <div class="pl-4 text-(--p-breadcrumb-item-color)">/Users/olha/lumlflow-demo</div>
    </div>
    <WorkspaceFolder :items="workspaceStore.sortedItems" class="mb-4" />
    <CreateNewFlow :existing-names="existingFlowNames" />
  </div>
</template>

<script setup lang="ts">
import { ROUTE_NAMES } from '@/router/router.const'
import { ChevronLeft } from 'lucide-vue-next'
import { computed } from 'vue'
import { useWorkspaceStore } from '@/store/workspace'
import WorkspaceFolder from '@/components/workspace/folder/WorkspaceFolder.vue'
import CreateNewFlow from '@/components/workspace/CreateNewFlow.vue'

const workspaceStore = useWorkspaceStore()

const existingFlowNames = computed(() =>
  workspaceStore.items.filter((item) => item.type === 'flow').map((item) => item.name),
)
</script>

<style scoped></style>
