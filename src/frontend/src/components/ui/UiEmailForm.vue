<template>
  <d-form
    class="form"
    v-slot="$form"
    :initialValues
    :resolver
    :validateOnValueUpdate="false"
    :validateOnSubmit="true"
    :validateOnBlur="true"
    @submit="onFormSubmit"
  >
    <div class="input-wrapper">
      <d-float-label variant="on">
        <d-input-text
          id="email"
          name="email"
          type="email"
          autocomplete="off"
          fluid
          v-model="initialValues.email"
          class="input"
          variant="filled"
        />
        <label for="email" class="label">Email</label>
      </d-float-label>
      <d-message
        v-if="$form.email?.invalid"
        severity="error"
        size="small"
        variant="simple"
        class="message"
      >
        {{ $form.email.error?.message }}
      </d-message>
    </div>
    <d-button type="submit" class="button" :loading="loading">
      <span>Get early access</span>
      <arrow-right :size="14" />
    </d-button>
  </d-form>
</template>

<script setup lang="ts">
import type { FormSubmitEvent } from '@primevue/forms'
import { ref } from 'vue'
import { ArrowRight } from 'lucide-vue-next'
import { useToast } from 'primevue'
import { simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { forgotPasswordInitialValues } from '@/utils/forms/initialValues'
import { forgotPasswordResolver } from '@/utils/forms/resolvers'
import { useRoute } from 'vue-router'
import { api } from '@/lib/api'

const toast = useToast()
const route = useRoute()

const initialValues = ref({ ...forgotPasswordInitialValues })
const resolver = ref(forgotPasswordResolver)
const loading = ref(false)

const onFormSubmit = async ({ valid, values }: FormSubmitEvent) => {
  if (!valid) return
  loading.value = true
  try {
    const currentPage = route.name
    await api.sendEmail({ email: values.email, description: currentPage as string })
    initialValues.value = { ...forgotPasswordInitialValues }
    toast.add(
      simpleSuccessToast(
        `We’ll notify you as soon as ${currentPage?.toString()} is ready for early access.`,
        'You’re on the list!',
      ),
    )
  } catch {
    toast.add({ severity: 'error', summary: 'Error', detail: 'Failed to send email' })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.form {
  max-width: 450px;
  width: 100%;
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.input-wrapper {
  flex: 1 1 auto;
  position: relative;
}

.input {
  height: 40px;
}

.message {
  position: absolute;
  top: calc(100% + 5px);
}

.button {
  flex: 0 0 auto;
  height: 40px;
}

@media (max-width: 768px) {
  .form {
    flex-direction: column;
    align-items: stretch;
    position: relative;
  }

  .input-wrapper {
    position: static;
  }
}
</style>
