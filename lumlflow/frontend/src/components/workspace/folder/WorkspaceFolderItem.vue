<template>
  <div v-if="item.type === 'file'" class="item">
    <div class="item-main-info text-muted-color-emphasis">
      <FileText :size="16" class="item-icon" />
      <span class="item-name">{{ item.name }}</span>
    </div>
    <span class="shrink-0">{{ getSizeText(item.size) }}</span>
  </div>
  <div v-else-if="item.type === 'folder'" class="item item-folder" @click="openFolder(item.path)">
    <div class="item-main-info text-muted-color-emphasis">
      <Folder :size="16" class="item-icon" />
      <span class="item-name">{{ item.name }}</span>
    </div>
  </div>
  <WorkspaceFolderItemFlow v-else-if="item.type === 'flow'" :item="item" />
</template>

<script setup lang="ts">
import type { IWorkspaceFolderItem } from '@/components/workspace/folder/interface'
import { FileText, Folder } from 'lucide-vue-next'
import { useToast } from 'primevue'
import { getSizeText } from '@/helpers/string'
import { errorToast } from '@/toasts'
import { useWorkspaceStore } from '@/store/workspace'
import WorkspaceFolderItemFlow from './WorkspaceFolderItemFlow.vue'

interface Props {
  item: IWorkspaceFolderItem
}

defineProps<Props>()

const toast = useToast()
const workspaceStore = useWorkspaceStore()

async function openFolder(path: string) {
  try {
    await workspaceStore.navigateToFolder(path)
  } catch (error) {
    toast.add(errorToast(error))
  }
}
</script>

<style scoped>
@reference "@/assets/css/index.css";

.item {
  @apply border-b border-(--p-datatable-body-cell-border-color) last:border-b-0 py-1 px-2 h-12.5 flex items-center justify-between gap-4;
}

.item-main-info {
  @apply flex items-center gap-2 overflow-hidden;
}

.item-icon {
  @apply shrink-0;
}

.item-name {
  @apply truncate;
}

.item-folder {
  @apply cursor-pointer transition-colors;
}

.item-folder:hover {
  background-color: var(--p-list-option-focus-background);
  border-radius: 8px;
}
</style>
