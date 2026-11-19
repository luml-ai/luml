<template>
  <div class="loader">
    <Skeleton width="422px" height="120px" />
    <Skeleton width="40%" height="16px" />
    <Skeleton v-for="index in 4" :key="index" height="24px" />
  </div>
</template>

<script setup lang="ts">
import { Skeleton } from 'primevue'
</script>

<style scoped>
.loader {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
</style>
