<template>
  <UiRightDialog
    v-model:visible="visible"
    :icon="PencilIcon"
    :title="dialogTitle"
    max-width="420px"
  >
    <AnnotationForm v-if="data" :data="data" :is-edit="true" @submit="onSubmit" />
    <template #footer>
      <Button severity="secondary" variant="outlined" @click="onCancel"> Cancel </Button>
      <Button type="submit" form="annotation-edit-form" severity="primary" :loading="loading"
        >Apply changes</Button
      >
    </template>
  </UiRightDialog>
</template>

<script setup lang="ts">
import type { Annotation, UpdateAnnotationPayload } from './annotations.interface'
import { PencilIcon } from 'lucide-vue-next'
import { Button, useToast } from 'primevue'
import { useAnnotationsStore } from '@/store/annotations'
import { computed, ref } from 'vue'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import UiRightDialog from '../ui/UiRightDialog.vue'
import AnnotationForm from './form/AnnotationForm.vue'

interface Props {
  artifactId: string
  data: Annotation | null
  type: 'eval' | 'span'
}

const props = defineProps<Props>()

const annotationsStore = useAnnotationsStore()

const toast = useToast()

const visible = defineModel<boolean>('visible', { default: false })

const loading = ref(false)

const dialogTitle = computed(() => {
  return `EDIT ${props.data?.name}`
})

async function onSubmit(data: UpdateAnnotationPayload) {
  if (loading.value) return
  loading.value = true
  try {
    if (!props.data) {
      throw new Error('Annotation data not found')
    }
    if (props.type === 'eval') {
      await annotationsStore.updateEvalAnnotation(props.artifactId, props.data.id, {
        value: data.value,
        rationale: data.rationale,
      })
    } else {
      await annotationsStore.updateSpanAnnotation(props.artifactId, props.data.id, {
        value: data.value,
        rationale: data.rationale,
      })
    }
    visible.value = false
    toast.add(simpleSuccessToast('Annotation updated successfully'))
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
