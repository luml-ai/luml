<template>
  <UiRightDialog
    v-model:visible="visible"
    :icon="PencilIcon"
    title="ADD ANNOTATION"
    max-width="420px"
  >
    <AnnotationForm :existing-names="existingNames" @submit="onSubmit" />
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
import type { AddAnnotationPayload, AnnotationFormInterface } from './annotations.interface'
import { PencilIcon, PlusIcon } from 'lucide-vue-next'
import { Button } from 'primevue'
import UiRightDialog from '../ui/UiRightDialog.vue'
import AnnotationForm from './form/AnnotationForm.vue'

type Props = {
  loading: boolean
  existingNames: string[]
}

type Emits = {
  (event: 'submit', data: AddAnnotationPayload): void
}

defineProps<Props>()

const emit = defineEmits<Emits>()

const visible = defineModel<boolean>('visible', { default: false })

async function onSubmit(data: AnnotationFormInterface) {
  const payload: AddAnnotationPayload = {
    annotation_kind: data.type,
    value_type: data.dataType,
    rationale: data.rationale,
    name: data.name,
    value: data.value,
  }
  emit('submit', payload)
}

function onCancel() {
  visible.value = false
}
</script>

<style scoped></style>
