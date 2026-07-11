<template>
  <div class="content">
    <!--<ImageInput
      shape="square"
      :image="Placeholder"
      class="photo"
      @on-image-change="onImageChange"
    />-->
    <Avatar size="xlarge" :label="avatarLabel" />
    <Form :initialValues :resolver @submit="onFormSubmit" class="body">
      <label for="name" class="label">Name</label>
      <InputText v-model="initialValues.name" name="name" id="name" class="input" />
      <Button type="submit" rounded fluid :loading="loading">Create</Button>
    </Form>
  </div>
</template>

<script setup lang="ts">
import { getErrorMessage } from '@/helpers/helpers'
import { InputText, Button, Avatar } from 'primevue'
import { computed, reactive, ref } from 'vue'
import { Form, type FormSubmitEvent } from '@primevue/forms'
import { zodResolver } from '@primevue/forms/resolvers/zod'
import { z } from 'zod'
import { useOrganizationStore } from '@/stores/organization'
import { useToast } from 'primevue'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'

type Emits = {
  close: []
}

const emits = defineEmits<Emits>()

const organizationStore = useOrganizationStore()
const toast = useToast()

const resolver = zodResolver(
  z.object({
    name: z.string().min(3).max(100),
  }),
)

const loading = ref(false)
const initialValues = reactive({
  name: '',
})

const avatarLabel = computed(() => {
  return initialValues.name.charAt(0).toUpperCase()
})

async function onFormSubmit({ values, valid }: FormSubmitEvent) {
  if (!valid) return
  const payload = {
    logo: 'https://framerusercontent.com/images/Ks0qcMuaRUt9YEMHOZIkAAXLwl0.png',
    name: values.name,
  }
  try {
    loading.value = true
    await organizationStore.createOrganization(payload)
    toast.add(simpleSuccessToast('All changes have been saved.'))
    emits('close')
  } catch (e: unknown) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Could not create organization')))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.photo {
  margin-bottom: 20px;
}
.body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.label {
  font-weight: 500;
}
.input {
  margin-bottom: 28px;
}
</style>
