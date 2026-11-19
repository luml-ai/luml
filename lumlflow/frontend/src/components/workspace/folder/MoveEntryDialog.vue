<template>
  <Dialog
    visible
    modal
    header="Move to"
    dismissable-mask
    :draggable="false"
    :pt="ENTRY_DIALOG_PT"
    :closable="!busy"
    :close-on-escape="!busy"
    @update:visible="(visible) => !visible && !busy && emit('close')"
  >
    <form id="workspace-move-form" @submit.prevent="move">
      <label for="move-folder" class="block mb-2"
        >Move <strong>{{ item.name }}</strong> to</label
      >
      <p class="text-xs text-muted-color break-all mb-2">{{ directory }}</p>
      <Select
        input-id="move-folder"
        fluid
        placeholder="Choose a folder"
        :options="options"
        option-label="name"
        option-value="path"
        option-disabled="disabled"
        :model-value="destination"
        :loading="loading"
        :disabled="loading || busy"
        @update:model-value="browse($event)"
      >
        <template #value>{{ destination ?? 'Choose a folder' }}</template>
        <template #empty>No folders in this directory</template>
      </Select>
      <Button
        v-if="nextOffset !== null"
        label="Show more folders"
        variant="text"
        size="small"
        :disabled="loading || busy"
        @click="browse(directory, nextOffset)"
      />
      <p v-if="item.type === 'file'" class="text-xs text-muted-color mt-2">{{ FILE_PATH_NOTE }}</p>
    </form>
    <template #footer>
      <Button
        type="submit"
        label="Move"
        :disabled="!destination || loading || busy"
        :loading="busy"
        form="workspace-move-form"
        fluid
        rounded
      />
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Button, Dialog, Select, useToast } from 'primevue'
import { parentDirectory } from '@/helpers/path'
import { workspaceApi } from '@/api/slices/workspace/workspace.api'
import type { WorkspaceFolder } from '@/api/slices/workspace/workspace.interface'
import { errorToast } from '@/toasts'
import { ENTRY_DIALOG_PT, FILE_PATH_NOTE, operationError } from './operations'
import type { IWorkspaceFolderItem } from './interface'

const props = defineProps<{
  item: IWorkspaceFolderItem
  start: string
  showHidden: boolean
  busy: boolean
}>()
const emit = defineEmits<{ close: []; move: [destination: string] }>()
const toast = useToast()
const directory = ref(props.start)
const destination = ref<string | null>(null)
const folders = ref<WorkspaceFolder[]>([])
const nextOffset = ref<number | null>(null)
const loading = ref(false)

const options = computed(() => {
  const parent = parentDirectory(directory.value)
  return [
    ...(parent ? [{ name: '↑ Parent folder', path: parent, disabled: false }] : []),
    ...folders.value.map(({ name, path }) => ({ name, path, disabled: path === props.item.path })),
  ]
})

async function browse(path: string, offset = 0) {
  if (loading.value) return
  loading.value = true
  try {
    const page = await workspaceApi.listFlows(path, props.showHidden, offset)
    directory.value = page.directory
    destination.value = page.directory === props.start ? null : page.directory
    folders.value = offset ? [...folders.value, ...page.folders] : page.folders
    // Files follow every folder in the daemon listing.
    nextOffset.value = page.files?.length ? null : (page.next_offset ?? null)
  } catch (error) {
    toast.add(errorToast(operationError(error)))
  } finally {
    loading.value = false
  }
}
function move() {
  if (destination.value && !loading.value && !props.busy) emit('move', destination.value)
}
onMounted(() => browse(props.start))
</script>
