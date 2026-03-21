<template>
  <div class="list">
    <AnnotationItem
      v-for="item in items"
      :key="item.id"
      :data="item"
      :is-editable="annotationsStore.isEditAvailable"
      @edit="onEdit(item)"
      @delete="onDelete(item)"
    />
  </div>

  <AnnotationEditDialog
    :visible="!!editDialogData"
    :data="editDialogData"
    :artifact-id="artifactId"
    :dataset-id="datasetId"
    :type="type"
    :existing-names="existingNames"
    @update:visible="onEditDialogVisibleUpdate"
  />
</template>

<script setup lang="ts">
import type { Annotation } from '../annotations.interface'
import { useConfirm, useToast } from 'primevue'
import { deleteAnnotationConfirmOptions } from '@/lib/primevue/data/confirm'
import { ref } from 'vue'
import { useAnnotationsStore } from '@/store/annotations'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import AnnotationItem from '../AnnotationItem.vue'
import AnnotationEditDialog from '../AnnotationEditDialog.vue'

interface Props {
  items: Annotation[]
  artifactId: string
  type: 'eval' | 'span'
  existingNames: string[]
  datasetId?: string
}

const annotationsStore = useAnnotationsStore()

const props = defineProps<Props>()

const confirm = useConfirm()

const toast = useToast()

const editDialogData = ref<Annotation | null>(null)

function onEdit(item: Annotation) {
  editDialogData.value = item
}

function onDelete(item: Annotation) {
  confirm.require(deleteAnnotationConfirmOptions(item.name, () => deleteAnnotation(item)))
}

async function deleteAnnotation(item: Annotation) {
  try {
    if (!props.artifactId) {
      throw new Error('Artifact ID is required')
    }
    if (props.type === 'span') {
      await annotationsStore.deleteSpanAnnotation(props.artifactId, item.id)
    } else {
      if (!props.datasetId) {
        throw new Error('Dataset ID is required')
      }
      await annotationsStore.deleteEvalAnnotation(props.artifactId, props.datasetId, item.id)
    }
    toast.add(simpleSuccessToast(`Annotation "${item.name}" deleted successfully`))
  } catch (error) {
    toast.add(simpleErrorToast(getErrorMessage(error)))
  }
}

function onEditDialogVisibleUpdate(visible: boolean) {
  if (!visible) editDialogData.value = null
}
</script>

<style scoped>
.list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  flex: 1 1 auto;
  overflow-y: auto;
}
</style>
