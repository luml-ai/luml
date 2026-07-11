<template>
  <div class="content">
    <h1 class="title">Error 404 <CircleX :size="42" color="var(--p-primary-color)" /></h1>
    <p class="text">We’re sorry, but the page you’re looking for does not exist.</p>
    <d-button as-child v-slot="slotProps">
      <RouterLink :to="{ name: 'home' }" :class="slotProps.class">Back to main</RouterLink>
    </d-button>
  </div>
</template>

<script setup lang="ts">
import { CircleX } from 'lucide-vue-next'
</script>

<style scoped>
.content {
  min-height: calc(100vh - 130px);
  max-width: 512px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-align: center;
}

.title {
  margin-bottom: 24px;
  font-size: 48px;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  gap: 12px;
}

.text {
  margin-bottom: 44px;
  font-size: 16px;
  line-height: 1.5;
  margin-bottom: 44px;
}
</style>
