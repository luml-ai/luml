<template>
  <authorization-wrapper title="Change email" :image="MainImage" :hide-sso="true">
    <template #form>
      <d-message v-if="success" severity="success"
        >Email changed successfully. Sign in with your new address.</d-message
      >
      <div v-else class="confirmation">
        <p v-if="newEmail">
          Change your account email to <strong>{{ newEmail }}</strong
          >?
        </p>
        <d-message v-else severity="error"
          >Email change link is expired, already used or invalid</d-message
        >
        <d-message v-if="error" severity="error">{{ error }}</d-message>
        <d-button
          v-if="newEmail"
          label="Confirm"
          :loading="pending"
          :disabled="pending"
          @click="confirm"
        />
      </div>
    </template>
    <template #footer>
      <router-link :to="{ name: 'sign-in' }" class="link">Sign in</router-link>
    </template>
  </authorization-wrapper>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import AuthorizationWrapper from '@/components/authorization/AuthorizationWrapper.vue'
import MainImage from '@/assets/img/form-bg.webp'
import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'
import { getErrorMessage } from '@/helpers/helpers'

const authStore = useAuthStore()
const token = new URLSearchParams(window.location.search).get('token') || ''
const success = ref(false)
const pending = ref(false)
const error = ref('')
const newEmail = (() => {
  try {
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
    return payload.type === 'email_change' && typeof payload.new_email === 'string'
      ? payload.new_email
      : ''
  } catch {
    return ''
  }
})()

const confirm = async () => {
  if (!newEmail || pending.value) return
  pending.value = true
  error.value = ''
  try {
    await api.confirmEmailChange(token)
    authStore.clearSession()
    success.value = true
  } catch (cause) {
    error.value = getErrorMessage(cause, 'Unable to confirm email change. Please try again.')
  } finally {
    pending.value = false
  }
}
</script>

<style scoped>
.confirmation {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
</style>
