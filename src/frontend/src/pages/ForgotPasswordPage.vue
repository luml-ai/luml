<template>
  <authorization-wrapper
    title="Forgot password?"
    sub-title="Enter your email to receive a new password"
    :image="MainImage"
    :hide-sso="true"
  >
    <template #form>
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
            />
            <label for="email" class="label">Email</label>
          </d-float-label>
          <d-message v-if="$form.email?.invalid" severity="error" size="small" variant="simple">
            {{ $form.email.error?.message }}
          </d-message>
        </div>
        <d-button type="submit" label="Send email" rounded />
      </d-form>
    </template>
    <template #footer>
      <router-link :to="{ name: 'sign-in' }" class="link">Back to Sign in</router-link>
    </template>
  </authorization-wrapper>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import AuthorizationWrapper from '@/components/authorization/AuthorizationWrapper.vue'

import MainImage from '@/assets/img/form-bg.webp'
import type { FormSubmitEvent } from '@primevue/forms'

import { useToast } from 'primevue/usetoast'
import { useAuthStore } from '@/stores/auth'

import { forgotPasswordInitialValues } from '@/utils/forms/initialValues'
import { forgotPasswordResolver } from '@/utils/forms/resolvers'
import { emailSentVerifyToast, unknownErrorToast } from '@/lib/primevue/data/toasts'

const toast = useToast()
const authStore = useAuthStore()

const initialValues = ref(forgotPasswordInitialValues)
const resolver = ref(forgotPasswordResolver)

const showSuccess = () => {
  toast.add(emailSentVerifyToast)
}

const onFormSubmit = async ({ valid }: FormSubmitEvent) => {
  if (!valid) return

  try {
    await authStore.forgotPassword(initialValues.value.email)
    showSuccess()
  } catch {
    toast.add(unknownErrorToast)
  }
}
</script>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: 25px;
}

.input-wrapper {
  display: flex;
  flex-direction: column;
  gap: 5px;
}
</style>
