<template>
  <d-message v-if="success" severity="success">{{ success }}</d-message>
  <d-form
    v-else
    v-slot="$form"
    :initialValues
    :resolver="userChangeEmailResolver"
    :validateOnValueUpdate="false"
    @submit="onSubmit"
    class="form"
  >
    <div>
      <d-float-label variant="on">
        <d-input-text id="new-email" name="new_email" type="email" autocomplete="email" fluid />
        <label for="new-email">New email</label>
      </d-float-label>
      <d-message v-if="$form.new_email?.invalid" severity="error" variant="simple">
        {{ $form.new_email.error?.message }}
      </d-message>
    </div>
    <div>
      <d-float-label variant="on">
        <d-password
          input-id="current-password"
          name="current_password"
          :input-props="{ autocomplete: 'current-password' }"
          :feedback="false"
          toggleMask
          fluid
        />
        <label for="current-password">Current password</label>
      </d-float-label>
      <d-message v-if="$form.current_password?.invalid" severity="error" variant="simple">
        {{ $form.current_password.error?.message }}
      </d-message>
    </div>
    <d-message v-if="error" severity="error" variant="simple">{{ error }}</d-message>
    <d-button type="submit" label="Send confirmation link" :loading="pending" :disabled="pending" />
  </d-form>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { FormSubmitEvent } from '@primevue/forms'
import { api } from '@/lib/api'
import { userChangeEmailResolver } from '@/utils/forms/resolvers'
import { getErrorMessage } from '@/helpers/helpers'

const initialValues = ref({ new_email: '', current_password: '' })
const success = ref('')
const error = ref('')
const pending = ref(false)

const onSubmit = async ({ valid, values }: FormSubmitEvent) => {
  if (!valid || pending.value) return
  pending.value = true
  error.value = ''
  try {
    const response = await api.changeEmail({
      new_email: values.new_email,
      current_password: values.current_password,
    })
    success.value = response.detail
  } catch (cause) {
    error.value = getErrorMessage(cause, 'Unable to request email change. Please try again.')
  } finally {
    pending.value = false
  }
}
</script>

<style scoped>
.form {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding-top: 10px;
}
</style>
