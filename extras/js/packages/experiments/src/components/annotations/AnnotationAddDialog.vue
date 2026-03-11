<template>
  <UiRightDialog
    v-model:visible="visible"
    :icon="PencilIcon"
    title="ADD ANNOTATION"
    max-width="420px"
  >
    <AnnotationForm @submit="onSubmit" />
    <template #footer>
      <Button severity="secondary" variant="outlined" @click="onCancel"> Cancel </Button>
      <Button type="submit" form="annotation-edit-form" severity="primary" :loading="loading">
        <PlusIcon :size="14" />
        Add annotation
      </Button>
    </template>
  </UiRightDialog>
</template>

<script setup lang="ts">
import { PencilIcon, PlusIcon } from 'lucide-vue-next'
import { Button, useToast } from 'primevue'
import { ref } from 'vue'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { useAnnotationsStore } from '@/store/annotations'
import { getErrorMessage } from '@/helpers/helpers'
import UiRightDialog from '../ui/UiRightDialog.vue'
import AnnotationForm from './form/AnnotationForm.vue'
import type { AnnotationFormInterface } from './annotations.interface'

type Props = {
  artifactId?: string
  datasetId?: string
  evalId?: string
}

const props = defineProps<Props>()

const toast = useToast()

const annotationsStore = useAnnotationsStore()

const visible = defineModel<boolean>('visible', { default: false })

const loading = ref(false)

async function onSubmit(data: AnnotationFormInterface) {
  if (loading.value) return
  loading.value = true
  try {
    if (!props.artifactId || !props.datasetId || !props.evalId) {
      throw new Error('Artifact ID, dataset ID and eval ID are required')
    }
    await annotationsStore.addEvalAnnotation(props.artifactId, props.datasetId, props.evalId, {
      annotation_kind: data.type,
      value_type: data.dataType,
      rationale: data.rationale,
      name: data.name,
      value: data.value,
    })
    visible.value = false
    toast.add(simpleSuccessToast('Annotation added successfully'))
  } catch (error) {
    toast.add(simpleErrorToast(getErrorMessage(error)))
  } finally {
    loading.value = false
  }
}

function onCancel() {
  visible.value = false
}
</script>

<style scoped></style>
