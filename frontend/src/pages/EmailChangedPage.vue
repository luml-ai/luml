<template>
  <authorization-wrapper
    :title="outcome.title"
    :sub-title="outcome.subTitle"
    :image="MainImage"
    :hide-sso="true"
  >
    <template #form>
      <d-button label="Go to sign in" rounded fluid @click="goToSignIn" />
    </template>
  </authorization-wrapper>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AuthorizationWrapper from '@/components/authorization/AuthorizationWrapper.vue'
import MainImage from '@/assets/img/form-bg.webp'
import { useAuthStore } from '@/stores/auth'

const OUTCOMES = {
  changed: {
    title: 'Email changed',
    subTitle: 'Your account email has been changed. Sign in with your new address.',
  },
  'in-use': {
    title: 'Email not changed',
    subTitle: 'This address is already used by another account.',
  },
  invalid: {
    title: 'Email not changed',
    subTitle:
      'This email change link has expired or is no longer valid. Request a new one in your profile settings.',
  },
}

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const status = computed(() => {
  const value = route.query.status
  return value === 'changed' || value === 'in-use' ? value : 'invalid'
})
const outcome = computed(() => OUTCOMES[status.value])

onMounted(() => {
  if (status.value === 'changed') authStore.clearSession()
})

function goToSignIn() {
  router.push({ name: 'sign-in' })
}
</script>
