<template>
  <div class="view" :style="{ minHeight: minBlockHeight }">
    <Lock :size="42"></Lock>
    <h1 class="view__title">Settings unavailable for your role</h1>
    <p class="view__text">
      You’re currently a member of this organization. To access these settings, you need admin or
      owner permissions.
    </p>
    <Button @click="$router.push({ name: 'home' })">Back to main</Button>
  </div>
</template>

<script setup lang="ts">
import { useLayout } from '@/hooks/useLayout'
import { Lock } from 'lucide-vue-next'
import { Button } from 'primevue'
import { computed } from 'vue'

const { headerSizes, footerSizes } = useLayout()

const minBlockHeight = computed(() => {
  return window.innerHeight - (headerSizes.value.height + footerSizes.value.height + 50) + 'px'
})
</script>

<style scoped>
.view {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-align: center;
  padding: 50px 0;
  max-width: 600px;
  margin: 0 auto;
}

.view__title {
  margin-top: 12px;
  margin-bottom: 24px;
  font-size: 28px;
  font-weight: 500;
}

.view__text {
  margin-bottom: 44px;
  line-height: 1.5;
}
</style>
