<template>
  <Dialog
    visible
    modal
    :header="`Create new ${type}`"
    dismissable-mask
    :draggable="false"
    :pt="ENTRY_DIALOG_PT"
    :closable="!busy"
    :close-on-escape="!busy"
    @update:visible="(visible) => !visible && !busy && emit('close')"
  >
    <form id="workspace-create-form" @submit.prevent="create">
      <label for="entry-name" class="inline-block mb-2 required">Name</label>
      <InputText
        v-model="name"
        id="entry-name"
        fluid
        autofocus
        required
        :disabled="busy"
        :invalid="!!errorMessage"
        :placeholder="type === 'folder' ? 'Name your folder' : 'Name your file, e.g. notes.md'"
        :aria-describedby="errorMessage ? 'entry-error' : undefined"
        @update:model-value="errorMessage = ''"
      />
      <Message v-if="errorMessage" id="entry-error" severity="error" size="small" variant="simple">
        {{ errorMessage }}
      </Message>
    </form>
    <template #footer>
      <Button
        type="submit"
        :label="`Create ${type}`"
        :disabled="!name || busy"
        :loading="busy"
        form="workspace-create-form"
        fluid
        rounded
      />
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Button, Dialog, InputText, Message, useToast } from 'primevue'
import { WorkspaceRefusedError, workspaceApi } from '@/api/slices/workspace/workspace.api'
import { errorToast } from '@/toasts'
import { ENTRY_DIALOG_PT, invalidName, operationError } from './operations'

const props = defineProps<{ type: 'folder' | 'file'; directory: string }>()
const emit = defineEmits<{ close: []; created: [path: string] }>()
const toast = useToast()
const name = ref('')
const busy = ref(false)
const errorMessage = ref('')

async function create() {
  if (busy.value) return
  errorMessage.value = invalidName(name.value)
  if (errorMessage.value) return
  busy.value = true
  try {
    const createEntry =
      props.type === 'folder' ? workspaceApi.createFolder : workspaceApi.createFile
    const result = await createEntry(props.directory, name.value)
    emit('created', result.path)
  } catch (error) {
    if (
      error instanceof WorkspaceRefusedError &&
      (error.kind === 'AlreadyExists' ||
        (error.kind === 'FlowError' && error.message.includes('single path component')))
    ) {
      errorMessage.value = error.message
    } else {
      toast.add(errorToast(operationError(error)))
    }
  } finally {
    busy.value = false
  }
}
</script>
