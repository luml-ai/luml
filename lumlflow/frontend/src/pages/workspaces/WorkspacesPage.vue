<template>
  <div>
    <div class="mb-6">
      <button
        class="inline-flex gap-0.5 items-center mb-1 cursor-pointer hover:text-primary transition-colors"
        @click="goUp"
      >
        <ChevronLeft :size="14" />
        <span>Workspace</span>
      </button>
      <div class="text-(--p-breadcrumb-item-color) truncate pl-4">
        {{ workspaceStore.currentDirectory }}
      </div>
    </div>
    <WorkspaceFolder :items="workspaceStore.sortedItems" class="mb-4" />
    <CreateNewFlow v-if="!workspaceStore.isDirectoryLoading" :existing-names="existingFlowNames" />
  </div>
</template>

<script setup lang="ts">
import { ChevronLeft } from 'lucide-vue-next'
import { useToast } from 'primevue'
import { computed, onBeforeMount } from 'vue'
import { useRoute } from 'vue-router'
import { useWorkspaceStore } from '@/store/workspace'
import { errorToast } from '@/toasts'
import WorkspaceFolder from '@/components/workspace/folder/WorkspaceFolder.vue'
import CreateNewFlow from '@/components/workspace/CreateNewFlow.vue'

const route = useRoute()
const toast = useToast()
const workspaceStore = useWorkspaceStore()

const existingFlowNames = computed(() =>
  workspaceStore.sortedItems.filter((item) => item.type === 'flow').map((item) => item.name),
)

async function goUp() {
  try {
    await workspaceStore.navigateUp()
  } catch (error) {
    toast.add(errorToast(error))
  }
}

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
