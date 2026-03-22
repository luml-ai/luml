<template>
  <div class="wrapper">
    <Skeleton style="height: 300px; width: 100%"></Skeleton>
    <Skeleton style="height: 300px; width: 100%"></Skeleton>
  </div>
</template>

<script setup lang="ts">
import { Skeleton } from 'primevue'
</script>

<style scoped>
.wrapper {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
  margin-bottom: 20px;
}
</style>
