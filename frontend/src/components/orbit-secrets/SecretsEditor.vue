<template>
  <Dialog
    :visible="props.visible"
    @update:visible="emit('update:visible', $event)"
    position="topright"
    :draggable="false"
    style="margin-top: 80px; height: 86%; width: 420px"
    :pt="dialogPt"
    modal
  >
    <template #header>
      <h2 class="dialog-title">
        <Bolt :size="20" color="var(--p-primary-color)" />
        <span>Secret settings</span>
      </h2>
    </template>

    <div v-if="isLoadingDetails" class="loading-container">
      <ProgressSpinner />
    </div>

    <Form
      v-else
      id="secret-edit-form"
      :initial-values="form"
      class="form"
      @submit="handleSubmit"
    >
      <div class="form-item">
        <label for="editSecretName" class="label">Name</label>
        <InputText v-model="form.name" id="editSecretName" name="name" :class="{ 'p-invalid': errors.name }" autofocus />
        <small v-if="errors.name" class="p-error">{{ errors.name }}</small>
      </div>

      <div class="form-item">
        <label for="editSecretValue" class="label">Key</label>
        <Password v-model="form.value" id="editSecretValue" name="value" :class="{ 'p-invalid': errors.value }" :feedback="false" toggleMask fluid />
        <small v-if="errors.value" class="p-error">{{ errors.value }}</small>
      </div>

      <div class="form-item">
        <label for="tags" class="label">Tags</label>
        <AutoComplete v-model="form.tags" id="tags" name="tags" :suggestions="autocompleteItems" @complete="searchTags" multiple fluid />
      </div>
    </Form>

    <template #footer>
      <div>
        <Button outlined severity="warn" :loading="isDeleting" :disabled="isLoadingDetails" @click="handleDelete">
          delete key
        </Button>
      </div>
      <Button type="submit" form="secret-edit-form" :loading="isSubmitting" :disabled="isLoadingDetails">
        save changes
      </Button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import { toRef } from 'vue'
import { Dialog, Button, InputText, Password, AutoComplete } from 'primevue'
import ProgressSpinner from 'primevue/progressspinner'
import { Form } from '@primevue/forms'
import { Bolt } from 'lucide-vue-next'
import type { OrbitSecret } from '@/lib/api/orbit-secrets/interfaces'
import { useSecretForm } from '@/hooks/useSecretForm'

interface Props {
  visible: boolean
  secret?: OrbitSecret | null
}
const props = defineProps<Props>()
const emit = defineEmits(['update:visible'])

const dialogPt = {
  footer: { style: 'display: flex; justify-content: space-between; width: 100%; margin-top: auto;' },
}

const {
  form,
  errors,
  isSubmitting,
  isDeleting,
  isLoadingDetails,
  autocompleteItems,
  searchTags,
  handleSubmit,
  handleDelete,
} = useSecretForm(toRef(props, 'secret'), { 
  onSuccess: () => emit('update:visible', false), 
})
</script>

<style scoped>
.dialog-title {
  font-weight: 500;
  font-size: 16px;
  text-transform: uppercase;
  display: flex;
  gap: 8px;
  align-items: center;
}
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
