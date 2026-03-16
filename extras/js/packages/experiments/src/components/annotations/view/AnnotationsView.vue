<template>
  <div class="view">
    <AnnotationsViewHeader :count="currentAnnotations.length" @close="close" />
    <AnnotationsViewList
      v-if="currentAnnotations.length && props.artifactId"
      :items="currentAnnotations"
      :artifact-id="props.artifactId"
      :type="props.evalId ? 'eval' : 'span'"
    />
    <div v-else class="empty">
      <div class="card-wrapper">
        <AnnotationAddCard v-if="annotationsStore.isEditAvailable" @add="openAddDialog" />
      </div>
    </div>
    <AnnotationAddButton
      v-if="annotationsStore.isEditAvailable"
      @add="openAddDialog"
      class="add-button"
    />
    <AnnotationAddDialog
      :visible="annotationsStore.isAddDialogVisible"
      :loading="loading"
      @update:visible="onAddDialogVisibleUpdate"
      @submit="addAnnotation"
    />
  </div>
</template>

<script setup lang="ts">
import type { AddAnnotationPayload } from '../annotations.interface'
import { computed, ref } from 'vue'
import { useAnnotationsStore } from '@/store/annotations'
import { useToast } from 'primevue'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import AnnotationsViewHeader from './AnnotationsViewHeader.vue'
import AnnotationsViewList from './AnnotationsViewList.vue'
import AnnotationAddCard from './AnnotationAddCard.vue'
import AnnotationAddButton from './AnnotationAddButton.vue'
import AnnotationAddDialog from '../AnnotationAddDialog.vue'

interface Emits {
  (event: 'close'): void
}

type Props = {
  artifactId?: string
  datasetId?: string
  evalId?: string
  traceId?: string
  spanId?: string
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const annotationsStore = useAnnotationsStore()
const toast = useToast()

const loading = ref(false)

const currentAnnotations = computed(() => {
  if (props.evalId) {
    return annotationsStore.evalAnnotations
  } else if (props.spanId) {
    return annotationsStore.spanAnnotations
  }
  return []
})

function onAddDialogVisibleUpdate(visible: boolean) {
  if (!visible) annotationsStore.closeAddDialog()
}

function openAddDialog() {
  try {
    if (props.evalId) {
      if (!props.artifactId || !props.datasetId || !props.evalId) {
        throw new Error('Artifact ID, dataset ID and eval ID are required')
      }
      annotationsStore.openAddDialog({
        artifactId: props.artifactId,
        datasetId: props.datasetId,
        evalId: props.evalId,
      })
    } else if (props.spanId) {
      if (!props.artifactId || !props.traceId || !props.spanId) {
        throw new Error('Artifact ID, trace ID and span ID are required')
      }
      annotationsStore.openAddDialog({
        artifactId: props.artifactId,
        traceId: props.traceId,
        spanId: props.spanId,
      })
    }
  } catch (error) {
    toast.add(simpleErrorToast(getErrorMessage(error, 'Failed to open add dialog')))
  }
}

function close() {
  emit('close')
  annotationsStore.closeAddDialog()
}

async function addAnnotation(data: AddAnnotationPayload) {
  if (loading.value) return
  loading.value = true
  try {
    if (props.evalId) {
      await annotationsStore.addEvalAnnotation(data)
    } else if (props.spanId) {
      await annotationsStore.addSpanAnnotation(data)
    } else {
      throw new Error('Trace ID or span ID is required')
    }
    annotationsStore.closeAddDialog()
    toast.add(simpleSuccessToast('Annotation added successfully'))
  } catch (error) {
    toast.add(simpleErrorToast(getErrorMessage(error, 'Failed to add annotation')))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.view {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: 100%;
  flex: 0 0 auto;
  width: 434px;
  padding: 0 20px 20px;
}

.view:not(:last-child) {
  border-right: 1px solid var(--p-divider-border-color);
}

.empty {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  flex: 1 1 auto;
  padding: 20px 0;
}

.card-wrapper {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-self: center;
}

.add-button {
  align-self: flex-end;
}
</style>
