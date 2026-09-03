<template>
  <div ref="itemRef" class="item">
    <RouterLink
      :to="{ name: ROUTE_NAMES.WORKSPACE_FLOW, query: { directory: item.path } }"
      class="item-link absolute inset-0"
    />
    <div class="item-main-info">
      <FileCodeCorner :size="16" color="var(--p-tabs-tab-active-color)" class="item-icon" />
      <div v-if="isRenaming" class="rename-block relative z-10">
        <InputText
          v-model="renameValue"
          class="max-w-50 max-h-6.5 rounded-none! shadow-none! border-x-0! border-t-0! px-0!"
        />
        <Button label="Save" severity="secondary" class="max-h-11" @click="saveName" />
      </div>
      <span v-else class="item-name">{{ item.name }}</span>
    </div>
    <Button
      severity="secondary"
      variant="text"
      class="relative z-10 shrink-0"
      aria-haspopup="menu"
      @click="menu?.toggle($event)"
    >
      <template #icon>
        <EllipsisVertical :size="16" />
      </template>
    </Button>
    <Menu ref="menu" :model="menuItems" popup />
  </div>
</template>

<script setup lang="ts">
import type { IWorkspaceFolderItem } from './interface'
import type { MenuItem } from 'primevue/menuitem'
import { Button, InputText, Menu, useConfirm, useToast } from 'primevue'
import { FileCodeCorner, EllipsisVertical } from 'lucide-vue-next'
import { ref, useTemplateRef } from 'vue'
import { onClickOutside, onKeyStroke } from '@vueuse/core'
import { deleteFlowConfirmOptions } from '@/confirm/confirm'
import { errorToast, successToast } from '@/toasts'
import { useWorkspaceStore } from '@/store/workspace'
import { FLOW_FILE_EXTENSION } from '@/components/workspace/workspace.const'
import { ROUTE_NAMES } from '@/router/router.const'

interface Props {
  item: IWorkspaceFolderItem
}

const props = defineProps<Props>()

const workspaceStore = useWorkspaceStore()

const confirm = useConfirm()
const toast = useToast()
const menu = useTemplateRef<InstanceType<typeof Menu>>('menu')
const itemRef = useTemplateRef<HTMLDivElement>('itemRef')

const isRenaming = ref(false)
const renameValue = ref('')

const menuItems: MenuItem[] = [
  { label: 'Rename', command: onRename },
  { label: 'Duplicate', command: onDuplicate },
  { label: 'Delete', command: onDelete },
]

function onRename() {
  renameValue.value = props.item.name
  isRenaming.value = true
}

function cancelRename() {
  isRenaming.value = false
}

function saveName() {
  const name = renameValue.value

  if (!name.endsWith(FLOW_FILE_EXTENSION)) {
    toast.add(errorToast(new Error(`Name must end with ${FLOW_FILE_EXTENSION}`)))
    return
  }

  const isTaken = workspaceStore.items.some(
    (item) => item.type === 'flow' && item.id !== props.item.id && item.name === name,
  )
  if (isTaken) {
    toast.add(errorToast(new Error(`"${name}" already exists`)))
    return
  }

  workspaceStore.renameFlow(props.item.id, name)
  toast.add(successToast('Flow renamed successfully'))
  isRenaming.value = false
}

onClickOutside(itemRef, cancelRename)
onKeyStroke('Escape', cancelRename)

function onDuplicate() {
  workspaceStore.duplicateFlow(props.item.id)
  toast.add(successToast('Flow duplicated successfully'))
}

function onDelete() {
  confirm.require(deleteFlowConfirmOptions(onDeleteConfirm))
}

function onDeleteConfirm() {
  workspaceStore.deleteFlow(props.item.id)
  toast.add(successToast('Flow deleted successfully'))
}
</script>

<style scoped>
@reference "@/assets/css/index.css";

.item {
  @apply relative border-b border-(--p-datatable-body-cell-border-color) last:border-b-0 py-1 px-2 h-12.5 flex items-center justify-between gap-4 transition-all;
}

.item:has(.item-link:hover) {
  background-color: var(--p-list-option-focus-background);
  border-radius: 8px;
}

.item:has(.item-link:hover) .item-name {
  color: var(--p-tabs-tab-active-color);
}

.item-main-info {
  @apply flex items-center gap-2 overflow-hidden;
}

.item-icon {
  @apply shrink-0;
}

.item-name {
  @apply truncate transition-colors;
}

.rename-block {
  @apply flex items-center gap-2;
}
</style>
