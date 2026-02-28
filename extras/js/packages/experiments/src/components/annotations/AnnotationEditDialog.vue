<template>
  <UiRightDialog
    v-model:visible="visible"
    :icon="PencilIcon"
    title="EDIT ANNONAME3"
    max-width="420px"
  >
    <AnnotationForm :data="data" />
    <template #footer>
      <Button severity="secondary" variant="outlined" @click="onCancel"> Cancel </Button>
      <Button severity="primary" @click="onSubmit">Apply changes</Button>
    </template>
  </UiRightDialog>
</template>

<script setup lang="ts">
import { PencilIcon } from 'lucide-vue-next'
import { Button } from 'primevue'
import UiRightDialog from '../ui/UiRightDialog.vue'
import AnnotationForm from './form/AnnotationForm.vue'

interface Props {
  data: any | null
}

defineProps<Props>()

const visible = defineModel<boolean>('visible', { default: false })

function onSubmit() {
  console.log('submit')
}

function onCancel() {
  visible.value = false
}
</script>

<style scoped></style>
