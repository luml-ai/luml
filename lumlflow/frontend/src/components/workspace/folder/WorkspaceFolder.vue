<template>
  <div>
    <Card>
      <template #content>
        <label class="flex justify-end items-center gap-2 text-sm text-muted-color mb-2">
          Show hidden
          <ToggleSwitch
            :model-value="pendingHidden ?? store.showHidden"
            :disabled="pendingHidden !== null"
            aria-label="Show hidden"
            @update:model-value="setHidden"
          />
        </label>
        <div v-if="store.isDirectoryLoading">
          <Skeleton v-for="i in 4" :key="i" height="40px" class="not-last:mb-1" />
        </div>
        <p v-else-if="items.length === 0" class="text-sm">This directory is empty</p>
        <template v-else>
          <WorkspaceFolderItem
            v-for="item in items"
            :key="item.path"
            :item="item"
            :selected="item.path === selectedPath"
            :compact="!!selectedPath"
            :renaming="renameTarget?.path === item.path"
            :busy="busy"
            @open="openItem"
            @menu="openMenu"
            @cancel="renameTarget = null"
            @rename="rename(item, $event)"
          />
          <div
            v-if="store.nextOffset != null"
            class="flex flex-wrap items-center justify-between mt-2 gap-2"
          >
            <span class="text-sm text-muted-color"
              >Showing {{ items.length.toLocaleString('en-US') }} of
              {{ store.total.toLocaleString('en-US') }} items</span
            >
            <Button
              label="Show more"
              variant="text"
              size="small"
              :loading="store.isLoadingMore"
              @click="report(store.loadMore())"
            />
          </div>
        </template>
      </template>
    </Card>
    <Menu ref="menu" popup :model="actions" />
    <div
      v-if="!store.isDirectoryLoading && store.currentDirectory"
      class="flex flex-wrap items-center gap-1 mt-4"
    >
      <CreateNewFlow :existing-names="existingFlowNames" />
      <Button variant="text" @click="createType = 'folder'"
        ><FolderPlus :size="16" />New folder</Button
      >
      <Button variant="text" @click="createType = 'file'"><FilePlus :size="16" />New file</Button>
    </div>
    <CreateEntryDialog
      v-if="createType && store.currentDirectory"
      :type="createType"
      :directory="store.currentDirectory"
      @close="createType = null"
      @created="created"
    />
    <MoveEntryDialog
      v-if="moveTarget && store.currentDirectory"
      :item="moveTarget"
      :start="store.currentDirectory"
      :show-hidden="store.showHidden"
      :busy="busy"
      @close="moveTarget = null"
      @move="move(moveTarget, $event)"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, useTemplateRef, watch } from 'vue'
import { Button, Card, Menu, Skeleton, ToggleSwitch, useConfirm, useToast } from 'primevue'
import type { ConfirmationOptions } from 'primevue/confirmationoptions'
import type { MenuItem } from 'primevue/menuitem'
import { FilePlus, FolderPlus } from 'lucide-vue-next'
import { WorkspaceRefusedError, workspaceApi } from '@/api/slices/workspace/workspace.api'
import { FLOW_FILE_EXTENSION } from '@/components/workspace/workspace.const'
import CreateNewFlow from '@/components/workspace/CreateNewFlow.vue'
import { useWorkspaceStore } from '@/store/workspace'
import { errorToast, successToast } from '@/toasts'
import CreateEntryDialog from './CreateEntryDialog.vue'
import MoveEntryDialog from './MoveEntryDialog.vue'
import WorkspaceFolderItem from './WorkspaceFolderItem.vue'
import type { IWorkspaceFolderItem } from './interface'
import { deleteConfirmation, invalidName, operationError } from './operations'

const props = defineProps<{
  items: IWorkspaceFolderItem[]
  selectedPath?: string | null
  beforeOperation?: (path: string) => Promise<boolean>
}>()
const emit = defineEmits<{
  'open-file': [path: string]
  'created-file': [path: string]
  navigate: [path: string]
}>()
const store = useWorkspaceStore()
const toast = useToast()
const confirm = useConfirm()
const menu = useTemplateRef('menu')
const menuTarget = ref<IWorkspaceFolderItem | null>(null)
const renameTarget = ref<IWorkspaceFolderItem | null>(null)
const moveTarget = ref<IWorkspaceFolderItem | null>(null)
const createType = ref<'file' | 'folder' | null>(null)
const busy = ref(false)
const pendingHidden = ref<boolean | null>(null)
const existingFlowNames = computed(() =>
  props.items.filter((item) => item.type === 'flow').map((item) => item.entryName ?? item.name),
)

watch(
  () => store.currentDirectory,
  () => {
    menu.value?.hide()
    menuTarget.value = renameTarget.value = moveTarget.value = null
    createType.value = null
  },
)

function openItem(item: IWorkspaceFolderItem) {
  if (item.type === 'folder') emit('navigate', item.path)
  if (item.type === 'file') emit('open-file', item.path)
}

function openMenu(event: MouseEvent, item: IWorkspaceFolderItem) {
  menuTarget.value = item
  menu.value?.toggle(event)
}

async function report(task: Promise<unknown>) {
  try {
    await task
  } catch (error) {
    toast.add(errorToast(operationError(error)))
  }
}

async function setHidden(value: boolean) {
  pendingHidden.value = value
  await report(store.setShowHidden(value))
  pendingHidden.value = null
}

async function created(path: string) {
  const directory = store.currentDirectory
  const file = createType.value === 'file'
  createType.value = null
  await report(store.refreshDirectory())
  if (file && directory === store.currentDirectory) emit('created-file', path)
}

function ask(options: ConfirmationOptions) {
  return new Promise<boolean>((resolve) =>
    confirm.require({
      ...options,
      accept: () => resolve(true),
      reject: () => resolve(false),
      onHide: () => resolve(false),
    }),
  )
}

const actions = computed<MenuItem[]>(() => {
  const item = menuTarget.value
  if (!item) return []
  return [
    { label: 'Rename', command: () => begin('rename', item) },
    ...(item.type === 'flow'
      ? [{ label: 'Duplicate', command: () => report(duplicate(item)) }]
      : []),
    { label: 'Move to…', command: () => begin('move', item) },
    { label: 'Delete', command: () => begin('delete', item) },
  ]
})

async function begin(action: 'rename' | 'move' | 'delete', item: IWorkspaceFolderItem) {
  if (busy.value) return
  const directory = store.currentDirectory
  if (props.beforeOperation && !(await props.beforeOperation(item.path))) return
  if (directory !== store.currentDirectory) return
  if (action === 'rename') renameTarget.value = item
  else if (action === 'move') moveTarget.value = item
  else if (await ask(deleteConfirmation(item))) {
    const remove = item.type === 'flow' ? workspaceApi.deleteFlow : workspaceApi.deleteFile
    await change(item, (close) => remove(item.path, close), 'deleted')
  }
}

async function duplicate(item: IWorkspaceFolderItem) {
  await store.duplicateFlow(item.path)
  toast.add(successToast('Notebook duplicated successfully'))
}

function rename(item: IWorkspaceFolderItem, name: string) {
  const error =
    invalidName(name) ||
    (item.type === 'flow' && !name.endsWith(FLOW_FILE_EXTENSION)
      ? `Name must end with ${FLOW_FILE_EXTENSION}`
      : '')
  if (error) {
    toast.add(errorToast(new Error(error)))
    return
  }
  if (name === (item.entryName ?? item.name)) {
    renameTarget.value = null
    return
  }
  const renameEntry = item.type === 'flow' ? workspaceApi.renameFlow : workspaceApi.renameFile
  void change(item, (close) => renameEntry(item.path, name, close), 'renamed')
}

function move(item: IWorkspaceFolderItem, destination: string) {
  const moveEntry = item.type === 'flow' ? workspaceApi.moveFlow : workspaceApi.moveFile
  void change(item, (close) => moveEntry(item.path, destination, close), 'moved')
}

async function change(
  item: IWorkspaceFolderItem,
  operation: (closeOpen: false | string[]) => Promise<unknown>,
  verb: 'renamed' | 'deleted' | 'moved',
) {
  if (busy.value) return
  busy.value = true
  try {
    // Inline rename leaves the viewer interactive until the new name is saved.
    if (verb === 'renamed' && props.beforeOperation && !(await props.beforeOperation(item.path)))
      return
    let close: false | string[] = false
    while (true) {
      try {
        await operation(close)
        break
      } catch (error) {
        if (!(error instanceof WorkspaceRefusedError) || error.kind !== 'FlowOpen') throw error
        const flows = error.details.flows ?? []
        if (!flows.length || flows.some((flow) => !flow.session_id)) throw error
        const subject = `${flows.length} open notebook${flows.length === 1 ? '' : 's'}`
        const names = flows.map((flow) => flow.name).join(', ')
        const proceed = await ask({
          header: 'Close open notebooks?',
          message: `${subject} will be closed: ${names}. Running cells stop and agents working in them lose their session. Close and continue?`,
          acceptProps: { label: 'Close and continue' },
          rejectProps: { label: 'Cancel' },
        })
        if (!proceed) return
        close = flows.map((flow) => flow.session_id)
      }
    }
    renameTarget.value = moveTarget.value = null
    if (item.type === 'flow') toast.add(successToast(`Notebook ${verb} successfully`))
    await report(store.refreshDirectory())
  } catch (error) {
    toast.add(errorToast(operationError(error)))
  } finally {
    busy.value = false
  }
}
</script>
