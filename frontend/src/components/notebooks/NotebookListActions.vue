<template>
  <Button variant="text" severity="secondary" rounded @click="toggleMenu">
    <template #icon>
      <EllipsisVertical :size="14" />
    </template>
  </Button>
  <Menu :model="menuItems" :popup="true" ref="menu">
    <template #itemicon="{ item }">
      <component :is="item.iconComponent" width="14" height="14" :color="item.color" />
    </template>
  </Menu>
  <Dialog v-model:visible="visible" modal header="Rename instance" :pt="dialogPt">
    <NotebookCreateUpdateForm
      v-if="editData"
      update-mode
      :initial-data="editData"
      @submit="onUpdateSubmit"
    >
    </NotebookCreateUpdateForm>
  </Dialog>
</template>

<script setup lang="ts">
import { getErrorMessage } from '@/helpers/helpers'
import type { MenuItem } from 'primevue/menuitem'
import type { Notebook } from '@/lib/databases/database.interfaces'
import { Menu, Button, Dialog, useConfirm, useToast, type DialogPassThroughOptions } from 'primevue'
import { DatabaseBackup, PenLine, Trash2, EllipsisVertical } from 'lucide-vue-next'
import { ref } from 'vue'
import { useNotebooksStore } from '@/stores/notebooks'
import NotebookCreateUpdateForm from './NotebookCreateUpdateForm.vue'

type Props = {
  notebook: Notebook
}

const dialogPt: DialogPassThroughOptions = {
  root: {
    style: 'max-width: 500px; width: 100%;',
  },
  header: {
    style: 'padding: 28px; text-transform: uppercase; font-size: 20px;',
  },
  content: {
    style: 'padding: 0 28px 28px;',
  },
}

const props = defineProps<Props>()

const confirm = useConfirm()
const toast = useToast()
const notebooksStore = useNotebooksStore()

const menuItems: MenuItem[] = [
  {
    label: 'Backup',
    iconComponent: DatabaseBackup,
    disabled: false,
    color: 'var(--p-primary-color)',
    command() {
      onBackupClick()
    },
  },
  {
    label: 'Rename',
    iconComponent: PenLine,
    color: 'var(--p-primary-color)',
    command() {
      onEditClick()
    },
  },
  {
    label: 'Delete',
    iconComponent: Trash2,
    color: 'var(--p-message-error-color)',
    command() {
      onDeleteClick()
    },
  },
]

const menu = ref()
const visible = ref(false)
const editData = ref<{ fullname?: string } | null>()

function toggleMenu(event: Event) {
  menu.value.toggle(event)
}

function onDeleteClick() {
  confirm.require({
    header: 'Delete this instance?',
    message:
      'Deleting this instance will remove all associated models. This action cannot be undone.',
    acceptProps: {
      label: 'delete',
      severity: 'warn',
      variant: 'outlined',
    },
    rejectProps: {
      label: 'cancel',
    },
    accept: async () => {
      try {
        await notebooksStore.remove(props.notebook.name)
        toast.add({
          severity: 'success',
          summary: 'Success',
          detail: 'Notebook deleted',
          life: 2000,
        })
      } catch (e: unknown) {
        toast.add({
          severity: 'error',
          summary: 'Error',
          detail: getErrorMessage(e, 'Failed to delete the instance'),
        })
      }
    },
  })
}
function onEditClick() {
  editData.value = { ...props.notebook }
  visible.value = true
}
async function onUpdateSubmit(payload: { fullname: string }) {
  visible.value = false
  await notebooksStore.edit({ ...editData.value, fullname: payload.fullname })
  toast.add({ severity: 'success', summary: 'Success', detail: 'Notebook info saved', life: 2000 })
}
function onBackupClick() {
  confirm.require({
    header: 'Create backup?',
    message: 'Your data is only stored in your browser. Make a backup to avoid losing it.',
    acceptProps: {
      label: 'confirm',
    },
    rejectProps: {
      label: 'cancel',
      severity: 'secondary',
    },
    accept: async () => {
      try {
        await notebooksStore.createBackup(props.notebook.name)
      } catch (e: unknown) {
        toast.add({
          severity: 'error',
          summary: 'Error',
          detail: getErrorMessage(e, 'Failed to create a backup'),
          life: 2000,
        })
      }
    },
  })
}
</script>

<style scoped></style>
