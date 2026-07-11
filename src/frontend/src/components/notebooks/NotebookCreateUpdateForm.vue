<template>
  <d-form
    v-slot="$form"
    :initialValues
    :resolver
    @submit="onFormSubmit"
    class="form"
    :validateOnValueUpdate="false"
    :validateOnSubmit="true"
    :validateOnBlur="false"
  >
    <div>
      <label class="label" for="fullname">{{ updateMode ? 'New name' : 'Name' }}</label>
      <d-input-text
        id="fullname"
        name="fullname"
        fluid
        v-model="initialValues.fullname"
        placeholder="Instance name"
      />
      <d-message v-if="$form.fullname?.invalid" severity="error" size="small" variant="simple">
        {{ $form.fullname.error?.message }}
      </d-message>
    </div>
    <Button type="submit" :loading="loading" :label="updateMode ? 'Confirm' : 'Create'" rounded />
  </d-form>
</template>

<script setup lang="ts">
import type { FormSubmitEvent } from '@primevue/forms'
import { ref } from 'vue'
import { z } from 'zod'
import { zodResolver } from '@primevue/forms/resolvers/zod'
import { Button } from 'primevue'

type Props = {
  updateMode?: true
  initialData?: { fullname?: string }
  loading?: boolean
}
type Emits = {
  submit: [{ fullname: string }]
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const initialValues = ref(props.initialData ? { ...props.initialData } : { fullname: '' })
const resolver = zodResolver(
  z.object({
    fullname: z.string().min(3),
  }),
)

function onFormSubmit({ values, valid }: FormSubmitEvent) {
  if (!valid) return
  const payload = { fullname: values.fullname }
  emit('submit', payload)
}
</script>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.label {
  display: inline-block;
  margin-bottom: 7px;
}
</style>
