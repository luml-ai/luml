<template>
  <Dialog
    v-model:visible="visible"
    header="Create a new secret"
    modal
    :draggable="false"
    :pt="dialogPt"
  >
    <Form id="secret-create-form" :initial-values="form"  class="form" @submit="handleSubmit">
      <div class="form-item">
        <label for="name" class="label required">Name</label>
        <InputText v-model="form.name" name="name" id="name" :class="{ 'p-invalid': errors.name }" autofocus />
        <small v-if="errors.name" class="p-error">{{ errors.name }}</small>
      </div>

      <div class="form-item">
        <label for="value" class="label required">Secret key</label>
        <Password v-model="form.value" name="value" id="value" :class="{ 'p-invalid': errors.value }" :feedback="false" toggleMask fluid />
        <small v-if="errors.value" class="p-error">{{ errors.value }}</small>
      </div>

      <div class="form-item">
        <label for="tags" class="label">Tags</label>
        <AutoComplete v-model="form.tags" id="tags" name="tags" :suggestions="autocompleteItems" @complete="searchTags" multiple fluid />
      </div>
    </Form>

    <template #footer>
      <Button type="submit" form="secret-create-form" fluid rounded :loading="isSubmitting">
        Create Secret
      </Button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Dialog, Button, InputText, Password, AutoComplete } from 'primevue'
import { Form } from '@primevue/forms'
import type { DialogPassThroughOptions } from 'primevue'
import { useSecretForm } from '@/hooks/useSecretForm'

const visible = defineModel<boolean>('visible')

const dialogPt: DialogPassThroughOptions = {
  root: { style: 'max-width: 500px; width: 100%;' },
  header: { style: 'padding: 28px; text-transform: uppercase; font-size: 20px;' },
  content: { style: 'padding: 0 28px 28px;' },
}

const {
  form,
  errors,
  isSubmitting,
  autocompleteItems,
  searchTags,
  handleSubmit,
  resetForm,
} = useSecretForm(ref(null), {
  onSuccess: () => { visible.value = false },
})

watch(visible, (newVisible) => {
  if (newVisible) resetForm()
})
</script>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.form-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.label {
  font-weight: 500;
  align-self: flex-start;
}
.p-error {
  color: var(--p-red-500);
  font-size: 12px;
}
.p-invalid {
  border-color: var(--p-red-500);
}
</style>
