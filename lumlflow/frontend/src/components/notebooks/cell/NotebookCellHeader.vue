<template>
  <header ref="headerRef" class="header">
    <div class="header-left overflow-hidden">
      <component
        :is="icon"
        :size="14"
        color="var(--p-button-text-secondary-color)"
        class="mt-1 shrink-0"
      />
      <div class="overflow-hidden">
        <div v-if="isRenaming" class="rename-block">
          <InputText
            ref="renameInputRef"
            v-model="renameValue"
            :disabled="isSaving"
            class="max-w-40 max-h-6.5 rounded-none! shadow-none! border-x-0! border-t-0! px-0!"
            @keyup.enter="saveName"
          />
          <Button
            label="Save"
            severity="secondary"
            size="small"
            :loading="isSaving"
            @click="saveName"
          />
        </div>
        <h3 v-else class="truncate">{{ title }}</h3>
        <div v-if="costSeconds !== null" class="text-sm text-muted-color">
          {{ costSeconds.toFixed(1) }}s
        </div>
      </div>
    </div>
    <div class="header-right shrink-0">
      <Button
        variant="outlined"
        severity="secondary"
        class="p-0 w-10 h-10"
        aria-haspopup="menu"
        @click="menu?.toggle($event)"
      >
        <template #icon>
          <EllipsisVertical :size="14" />
        </template>
      </Button>
      <Menu ref="menu" :model="menuItems" popup :pt="CELL_HEADER_MENU_PT">
        <template #itemicon="{ item }">
          <component :is="(item as CellHeaderMenuItem).glyph" :size="14" class="shrink-0" />
        </template>
      </Menu>
    </div>
  </header>
</template>

<script setup lang="ts">
import type {
  CellHeaderMenuItem,
  NotebookCellHeaderProps,
} from '@/components/notebooks/cell/cell.interface'
import { Button, InputText, Menu, useConfirm, useToast } from 'primevue'
import { nextTick, ref, useTemplateRef } from 'vue'
import { onClickOutside, onKeyStroke } from '@vueuse/core'
import {
  CloudUpload,
  Copy,
  Download,
  EllipsisVertical,
  Maximize2,
  Notebook,
  Pencil,
  Plus,
  Send,
  Trash2,
  Workflow,
} from 'lucide-vue-next'
import { deleteCellConfirmOptions } from '@/confirm/confirm'
import { errorToast, successToast } from '@/toasts'
import { useFlowStore } from '@/store/flow'
import { useDownload } from '@/hooks/useDownload'
import { CELL_HEADER_MENU_PT, CELL_NAME_UNSAFE } from '@/components/notebooks/cell/cell.const'

const props = defineProps<NotebookCellHeaderProps>()

const flowStore = useFlowStore()
const toast = useToast()
const confirm = useConfirm()
const { download } = useDownload()

const menu = useTemplateRef<InstanceType<typeof Menu>>('menu')
const headerRef = useTemplateRef<HTMLElement>('headerRef')
const renameInputRef = useTemplateRef<{ $el: HTMLInputElement }>('renameInputRef')

const isRenaming = ref(false)
const renameValue = ref('')
const isSaving = ref(false)

function validateCellName(name: string): string | null {
  if (!name) return 'Name is required'
  if (name.startsWith('.')) return 'Name cannot start with a dot'
  if (name.includes('..')) return 'Name cannot contain ".."'
  if (CELL_NAME_UNSAFE.test(name)) return 'Name contains invalid characters'
  const isTaken = flowStore.cells.some(
    (cell) => cell.slug !== props.cell.slug && cell.slug.toLowerCase() === name.toLowerCase(),
  )
  if (isTaken) return `"${name}" already exists`
  return null
}

async function onRename() {
  renameValue.value = props.cell.slug
  isRenaming.value = true
  await nextTick()
  const input = renameInputRef.value?.$el
  if (!input) return
  input.focus()
  input.setSelectionRange(input.value.length, input.value.length)
}

function cancelRename() {
  isRenaming.value = false
}

async function saveName() {
  const name = renameValue.value.trim()
  if (name === props.cell.slug) {
    isRenaming.value = false
    return
  }

  const error = validateCellName(name)
  if (error) {
    toast.add(errorToast(new Error(error)))
    return
  }

  isSaving.value = true
  try {
    await flowStore.renameCell(props.cell.slug, name)
    toast.add(successToast('Cell renamed successfully'))
    isRenaming.value = false
  } catch (error) {
    toast.add(errorToast(error))
  } finally {
    isSaving.value = false
  }
}

onClickOutside(headerRef, cancelRename)
onKeyStroke('Escape', cancelRename)

async function onDuplicate() {
  try {
    const newSlug = await flowStore.duplicateCell(props.cell.slug)
    flowStore.selectCell(newSlug)
    toast.add(successToast('Cell duplicated successfully'))
  } catch (error) {
    toast.add(errorToast(error))
  }
}

async function onAddCellDownstream() {
  try {
    const newSlug = await flowStore.addCellDownstream(props.cell.slug)
    flowStore.selectCell(newSlug)
    toast.add(successToast('Cell added downstream'))
  } catch (error) {
    toast.add(errorToast(error))
  }
}

function onGoToNotebook() {
  flowStore.setViewMode('notebook')
  flowStore.selectCell(props.cell.slug)
}

function onGoToCanvas() {
  flowStore.setViewMode('canvas')
  flowStore.selectCell(props.cell.slug)
}

async function onDownload() {
  try {
    const source = await flowStore.fetchCellSource(props.cell.slug)
    download(source, `${props.cell.slug}.py`, 'text/x-python')
  } catch (error) {
    toast.add(errorToast(error))
  }
}

function onDelete() {
  confirm.require(deleteCellConfirmOptions(onDeleteConfirm, props.cell.slug))
}

async function onDeleteConfirm() {
  try {
    await flowStore.deleteCell(props.cell.slug)
    toast.add(successToast('Cell deleted successfully'))
  } catch (error) {
    toast.add(errorToast(error))
  }
}

const menuItems: CellHeaderMenuItem[] = [
  {
    label: 'Expand',
    glyph: Maximize2,
    command: () => flowStore.setExpandedCellId(props.cell.slug),
  },
  { label: 'Rename', glyph: Pencil, command: onRename },
  { label: 'Duplicate', glyph: Copy, command: onDuplicate },
  {
    label: 'Add cell downstream',
    glyph: Plus,
    command: onAddCellDownstream,
  },
  {
    label: 'Go to Notebook',
    glyph: Notebook,
    visible: () => flowStore.viewMode === 'canvas',
    command: onGoToNotebook,
  },
  {
    label: 'Go to Canvas',
    glyph: Workflow,
    visible: () => flowStore.viewMode === 'notebook',
    command: onGoToCanvas,
  },
  { separator: true },
  { label: 'Send to agent', glyph: Send, command: () => console.log('Send to agent') },
  { label: 'Promote to LUML', glyph: CloudUpload, command: () => console.log('Promote to LUML') },
  { label: 'Download', glyph: Download, command: onDownload },
  { separator: true },
  {
    label: 'Delete from this lane',
    glyph: Trash2,
    class: 'notebook-cell-menu-danger',
    command: onDelete,
  },
]
</script>

<style scoped>
@reference "@/assets/css/index.css";

.header {
  @apply flex items-center justify-between gap-4;
}
.header-left {
  @apply flex items-center gap-1 min-h-10;
}
.rename-block {
  @apply flex items-center gap-2 mb-1;
}
.status-circle {
  @apply w-5 h-5 shrink-0 rounded-full bg-(--p-toast-success-background) border border-(--p-toast-success-border-color) flex items-center justify-center;
}
.status-circle::before {
  @apply content-[''] w-3 h-3 rounded-full bg-(--p-badge-success-background) shadow-[0px_2px_8px_0px_#22C55E80];
}
</style>

<style>
.notebook-cell-menu-danger .p-menu-item-content {
  color: var(--p-button-text-warn-color);
}
</style>
