<template>
  <div class="offer">
    <MonitorCheck :size="42" color="var(--p-button-primary-background)" />
    <h1 class="title">This section is only available on desktop</h1>
    <h2 class="text">
      This feature requires desktop access. Please use a computer with a larger screen to view this
      content.
    </h2>
    <d-button asChild v-slot="slotProps">
      <RouterLink :to="{ name: 'home' }" :class="slotProps.class">Back to main</RouterLink>
    </d-button>
  </div>
</template>

<script setup lang="ts">
import { MonitorCheck } from 'lucide-vue-next'
</script>

<style scoped>
.offer {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  max-width: 387px;
  margin: 0 auto;
  text-align: center;
}
.title {
  margin-top: 12px;
  margin-bottom: 24px;
  font-size: 28px;
}
.text {
  font-size: 16px;
  margin-bottom: 44px;
}
</style>
