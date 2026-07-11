<template>
  <authorization-wrapper
    title="Email confirmed!"
    sub-title="Thank you for verifying your email address. Your account is now fully activated, and you can proceed to access all the features of our platform."
    :image="MainImage"
    :hide-sso="true"
  >
    <template #form>
      <d-button
        type="submit"
        label="Go to account"
        rounded
        fluid
        @click="$router.push({ name: 'sign-in' })"
      />
    </template>
  </authorization-wrapper>
</template>

<script setup lang="ts">
import AuthorizationWrapper from '@/components/authorization/AuthorizationWrapper.vue'

import MainImage from '@/assets/img/form-bg.webp'
</script>
