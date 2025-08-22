<template>
  <header class="header">
    <h2 class="title">Multi-model comparison</h2>
    <Button severity="secondary">
      <Bolt :size="14"></Bolt>
      <span>View settings</span>
    </Button>
  </header>
</template>

<script setup lang="ts">
import { Button } from 'primevue'
import { Bolt } from 'lucide-vue-next'
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 20px;
}
</style>
