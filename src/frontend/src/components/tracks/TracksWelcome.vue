<template>
  <div class="card">
    <TrainTrack :size="35" color="var(--p-primary-color)" />
    <h3 class="title">Get started with Tracks</h3>
    <p class="text">
      Track your best artifacts across versions and stages — from Staging to Production.
    </p>
  </div>
</template>

<script setup lang="ts">
import { TrainTrack } from 'lucide-vue-next'
</script>

<style scoped>
.card {
  padding: 16px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  box-shadow: var(--card-shadow);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-align: center;
  gap: 8px;
  min-height: 150px;
}
.title {
  font-size: 16px;
}
.text {
  font-size: 12px;
  color: var(--p-text-muted-color);
}
</style>
