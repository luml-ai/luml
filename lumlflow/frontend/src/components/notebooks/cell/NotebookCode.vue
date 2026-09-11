<template>
  <p v-if="isLoading" class="text-sm text-muted-color">Loading code…</p>
  <div v-else class="flex flex-col gap-2 nowheel nodrag">
    <div class="flex justify-end gap-2">
      <template v-if="isEditing">
        <Button
          text
          severity="secondary"
          label="Cancel"
          size="small"
          :disabled="isSaving"
          @click="onCancel"
        />
        <Button
          label="Save"
          size="small"
          :loading="isSaving"
          :disabled="isSaving"
          @click="onSave"
        />
      </template>
      <Button v-else text severity="secondary" label="Edit" size="small" @click="onEdit">
        <template #icon>
          <Pencil :size="14" />
        </template>
      </Button>
    </div>

    <UiCodeEditor v-if="isEditing" v-model="draftSource" :aria-label="`source of ${props.slug}`" />
    <pre v-else class="code-output">{{ source }}</pre>
  </div>
</template>

<script setup lang="ts">
import type { NotebookCodeProps } from '@/components/notebooks/cell/cell.interface'
import { onBeforeMount, ref } from 'vue'
import { Button } from 'primevue'
import { useToast } from 'primevue/usetoast'
import { Pencil } from 'lucide-vue-next'
import { errorToast, successToast } from '@/toasts'
import { useFlowStore } from '@/store/flow'
import UiCodeEditor from '@/components/ui/code-editor/UiCodeEditor.vue'

const props = defineProps<NotebookCodeProps>()

const flowStore = useFlowStore()
const toast = useToast()

const source = ref('')
const draftSource = ref('')
const isLoading = ref(false)
const isEditing = ref(false)
const isSaving = ref(false)

onBeforeMount(async () => {
  isLoading.value = true
  try {
    source.value = await flowStore.fetchCellSource(props.slug)
  } catch (error) {
    toast.add(errorToast(error, 'Failed to load code'))
  } finally {
    isLoading.value = false
  }
})

function onEdit() {
  draftSource.value = source.value
  isEditing.value = true
}

function onCancel() {
  isEditing.value = false
}

async function onSave() {
  isSaving.value = true
  try {
    await flowStore.editCellSource(props.slug, draftSource.value)
    source.value = draftSource.value
    isEditing.value = false
    toast.add(successToast('Code saved successfully'))
  } catch (error) {
    toast.add(errorToast(error, 'Failed to save code'))
  } finally {
    isSaving.value = false
  }
}
</script>

<style scoped>
@reference "@/assets/css/index.css";

.code-output {
  @apply max-h-64 overflow-auto whitespace-pre-wrap wrap-break-word rounded-lg border border-surface bg-surface-50 dark:bg-surface-900 p-3 font-mono text-sm leading-relaxed;
}
</style>
