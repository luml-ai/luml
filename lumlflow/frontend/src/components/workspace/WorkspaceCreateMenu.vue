<template>
  <div>
    <template v-if="!store.isDirectoryLoading && store.currentDirectory">
      <Button v-if="store.isNotebookListing" label="New notebook" @click="flowDialog?.open()">
        <template #icon><Plus :size="14" /></template>
      </Button>
      <SplitButton v-else label="New notebook" :model="entries" @click="flowDialog?.open()">
        <template #icon><Plus :size="14" /></template>
        <template #menuitemicon="{ item }">
          <component :is="(item as CreateMenuItem).glyph" :size="14" />
        </template>
      </SplitButton>
    </template>
    <CreateNewFlow ref="flowDialog" :existing-names="existingFlowNames" />
    <CreateEntryDialog
      v-if="createType && store.currentDirectory"
      :type="createType"
      :directory="store.currentDirectory"
      @close="createType = null"
      @created="created"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, useTemplateRef, watch, type Component } from 'vue'
import { Button, SplitButton, useToast } from 'primevue'
import type { MenuItem } from 'primevue/menuitem'
import { FilePlus, FolderPlus, Plus } from 'lucide-vue-next'
import CreateNewFlow from '@/components/workspace/CreateNewFlow.vue'
import CreateEntryDialog from '@/components/workspace/folder/CreateEntryDialog.vue'
import { operationError } from '@/components/workspace/folder/operations'
import { useWorkspaceStore } from '@/store/workspace'
import { errorToast } from '@/toasts'

type CreateMenuItem = MenuItem & { glyph: Component }

const emit = defineEmits<{ 'created-file': [path: string] }>()
const store = useWorkspaceStore()
const toast = useToast()
const flowDialog = useTemplateRef('flowDialog')
const createType = ref<'file' | 'folder' | null>(null)
const existingFlowNames = computed(() =>
  store.sortedItems
    .filter((item) => item.type === 'flow')
    .map((item) => item.entryName ?? item.name),
)
const entries: CreateMenuItem[] = [
  { label: 'New folder', glyph: FolderPlus, command: () => (createType.value = 'folder') },
  { label: 'New file', glyph: FilePlus, command: () => (createType.value = 'file') },
]

watch(
  () => store.currentDirectory,
  () => (createType.value = null),
)

async function created(path: string) {
  const directory = store.currentDirectory
  const file = createType.value === 'file'
  createType.value = null
  try {
    await store.refreshDirectory()
  } catch (error) {
    toast.add(errorToast(operationError(error)))
  }
  if (file && directory === store.currentDirectory) emit('created-file', path)
}
</script>
