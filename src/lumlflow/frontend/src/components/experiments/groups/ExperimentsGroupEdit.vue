<template>
  <RightFullHeightDialog title="Group settings" :icon="Bolt" v-model:visible="visible">
    <Form
      v-if="groupsStore.editableGroup"
      id="group-edit-form"
      :resolver="experimentGroupResolver"
      :initialValues="groupsStore.editableGroup"
      class="flex flex-col gap-5"
      @submit="onSubmit"
    >
      <FormField name="name">
        <label for="name" class="inline-block mb-2">Name</label>
        <InputText id="name" fluid placeholder="Name your group" />
      </FormField>
      <FormField name="description">
        <label for="description" class="inline-block mb-2">Description</label>
        <InputText id="description" fluid placeholder="Describe your group" />
      </FormField>
      <FormField name="tags">
        <label :for="tagsId" class="inline-block mb-2">Tags</label>
        <UiTagsSelect :id="tagsId" :items="[]" placeholder="Select tags" />
      </FormField>
    </Form>
    <template #footer>
      <div class="flex gap-2 justify-between w-full">
        <Button label="delete group" severity="warn" variant="outlined" @click="onDelete" />
        <Button label="save changes" type="submit" form="group-edit-form" :loading="isSubmitting" />
      </div>
    </template>
  </RightFullHeightDialog>
</template>

<script setup lang="ts">
import { Bolt } from 'lucide-vue-next'
import { Button, InputText, useConfirm, useToast } from 'primevue'
import { Form, FormField, type FormSubmitEvent } from '@primevue/forms'
import { ref, useId } from 'vue'
import { experimentGroupResolver } from '@/forms/resolvers/experiment-groups'
import { useGroupsStore } from '@/store/groups'
import { watch } from 'vue'
import { deleteGroupConfirmOptions } from '@/confirm/confirm'
import { errorToast } from '@/toasts'
import RightFullHeightDialog from '@/dialogs/RightFullHeightDialog.vue'
import UiTagsSelect from '@/components/ui/UiTagsSelect.vue'

const tagsId = useId()
const groupsStore = useGroupsStore()
const confirm = useConfirm()
const toast = useToast()

const visible = ref(false)
const isSubmitting = ref(false)

function onDelete() {
  confirm.require(
    deleteGroupConfirmOptions(() => {
      if (!groupsStore.editableGroup) return
      groupsStore.deleteGroups([groupsStore.editableGroup.id])
    }),
  )
}

async function onSubmit(event: FormSubmitEvent) {
  if (!event.valid) return
  if (isSubmitting.value) return
  if (!groupsStore.editableGroup) return
  try {
    isSubmitting.value = true
    const payload = createPayload(event)
    await groupsStore.updateGroup(groupsStore.editableGroup.id, payload)
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
  () => groupsStore.editableGroup,
  (group) => {
    if (group) {
      visible.value = true
    } else {
      visible.value = false
    }
  },
  { immediate: true },
)

watch(visible, (visible) => {
  if (!visible) {
    groupsStore.setEditableGroup(null)
  }
})
</script>

<style scoped></style>
