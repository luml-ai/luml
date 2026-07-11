<template>
  <authorization-wrapper
    title="Check your email"
    sub-title="Thank you for signing up! You should see a verification link in your email (it might be in your spam folder)."
    :image="MainImage"
    :hide-sso="true"
  >
    <template #form>
      <d-button
        type="submit"
        label="Use another account"
        rounded
        fluid
        @click="$router.push({ name: 'sign-up' })"
      />
    </template>
    <!--<template #footer>
      <span>Did not receive it?</span>
      <router-link :to="{ name: 'sign-in' }" class="link"> Resend link</router-link>
    </template>-->
  </authorization-wrapper>
</template>

<script setup lang="ts">
import AuthorizationWrapper from '@/components/authorization/AuthorizationWrapper.vue'

import MainImage from '@/assets/img/form-bg.webp'
</script>
