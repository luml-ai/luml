<template>
  <RightFullHeightDialog title="Experiment settings" :icon="Bolt" v-model:visible="visible">
    <Form
      v-if="experimentsStore.editableExperiment"
      id="experiment-edit-form"
      :resolver="experimentResolver"
      :initialValues="experimentsStore.editableExperiment"
      class="flex flex-col gap-5"
      @submit="onSubmit"
    >
      <FormField name="name">
        <label for="name" class="inline-block mb-2">Name</label>
        <InputText id="name" fluid placeholder="Name your experiment" />
      </FormField>
      <FormField name="description">
        <label for="description" class="inline-block mb-2">Description</label>
        <InputText id="description" fluid placeholder="Describe your experiment" />
      </FormField>
      <FormField name="tags">
        <label :for="tagsId" class="inline-block mb-2">Tags</label>
        <UiTagsSelect :id="tagsId" :items="[]" placeholder="Select tags" />
      </FormField>
    </Form>
    <template #footer>
      <div class="flex gap-2 justify-between w-full">
        <Button label="delete experiment" severity="warn" variant="outlined" @click="onDelete" />
        <Button
          label="save changes"
          type="submit"
          form="experiment-edit-form"
          :loading="isSubmitting"
        />
      </div>
    </template>
  </RightFullHeightDialog>
</template>

<script setup lang="ts">
import { Bolt } from 'lucide-vue-next'
import { Button, InputText, useConfirm, useToast } from 'primevue'
import { Form, FormField, type FormSubmitEvent } from '@primevue/forms'
import { ref, useId } from 'vue'
import { experimentResolver } from '@/forms/resolvers/experiment'
import { useExperimentsStore } from '@/store/experiments'
import { watch } from 'vue'
import { deleteExperimentConfirmOptions } from '@/confirm/confirm'
import { errorToast } from '@/toasts'
import RightFullHeightDialog from '@/dialogs/RightFullHeightDialog.vue'
import UiTagsSelect from '@/components/ui/UiTagsSelect.vue'

const tagsId = useId()
const experimentsStore = useExperimentsStore()
const confirm = useConfirm()
const toast = useToast()

const visible = ref(false)
const isSubmitting = ref(false)

function onDelete() {
  confirm.require(
    deleteExperimentConfirmOptions(() => {
      if (!experimentsStore.editableExperiment) return
      experimentsStore.deleteExperiments([experimentsStore.editableExperiment.id])
    }),
  )
}

async function onSubmit(event: FormSubmitEvent) {
  if (!event.valid) return
  if (isSubmitting.value) return
  if (!experimentsStore.editableExperiment) return
  try {
    isSubmitting.value = true
    const payload = createPayload(event)
    await experimentsStore.updateExperiment(experimentsStore.editableExperiment.id, payload)
    visible.value = false
  } catch (error) {
    toast.add(errorToast(error))
  } finally {
    isSubmitting.value = false
  }
}

function createPayload(event: FormSubmitEvent) {
  return {
    name: event.values.name,
    description: event.values.description,
    tags: event.values.tags,
  }
}

watch(
  () => experimentsStore.editableExperiment,
  (experiment) => {
    if (experiment) {
      visible.value = true
    } else {
      visible.value = false
    }
  },
  { immediate: true },
)

watch(visible, (visible) => {
  if (!visible) {
    experimentsStore.setEditableExperiment(null)
  }
})
</script>

<style scoped></style>
