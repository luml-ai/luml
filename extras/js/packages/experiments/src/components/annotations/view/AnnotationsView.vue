<template>
  <div class="view">
    <AnnotationsViewHeader :count="annotationsStore.evalAnnotations.length" @close="close" />
    <AnnotationsViewList
      v-if="annotationsStore.evalAnnotations.length"
      :items="annotationsStore.evalAnnotations"
      :artifact-id="props.artifactId"
    />
    <div v-else class="empty">
      <div class="card-wrapper">
        <AnnotationAddCard v-if="annotationsStore.isEditAvailable" @add="onAdd" />
      </div>
    </div>
    <AnnotationAddButton v-if="annotationsStore.isEditAvailable" @add="onAdd" class="add-button" />
    <AnnotationAddDialog
      :visible="annotationsStore.isAddDialogVisible"
      :artifact-id="props.artifactId"
      :dataset-id="props.datasetId"
      :eval-id="props.evalId"
      @update:visible="onAddDialogVisibleUpdate"
    />
  </div>
</template>

<script setup lang="ts">
import { useAnnotationsStore } from '@/store/annotations'
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
}

const props = defineProps<Props>()

const emit = defineEmits<Emits>()

const annotationsStore = useAnnotationsStore()

function onAddDialogVisibleUpdate(visible: boolean) {
  if (!visible) annotationsStore.closeAddDialog()
}

function onAdd() {
  if (!props.artifactId || !props.datasetId || !props.evalId) {
    throw new Error('Artifact ID, dataset ID and eval ID are required')
  }
  annotationsStore.openAddDialog(props.artifactId, props.datasetId, props.evalId)
}

function close() {
  emit('close')
  annotationsStore.closeAddDialog()
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
