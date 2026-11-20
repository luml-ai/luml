<template>
  <div class="loader">
    <div class="spans">
      <Skeleton width="40%" height="20px" />
      <Skeleton v-for="index in 3" :key="index" height="64px" />
    </div>
    <div class="body">
      <Skeleton width="30%" height="20px" />
      <Skeleton width="50%" height="36px" />
      <Skeleton v-for="index in 3" :key="index" height="96px" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { Skeleton } from 'primevue'
</script>

<style scoped>
.loader {
  display: flex;
  height: 100%;
}

.spans {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 320px;
  flex-shrink: 0;
  padding: 20px;
  border-right: 1px solid var(--p-divider-border-color);
}

.body {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  padding: 20px;
}
</style>
