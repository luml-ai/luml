<template>
  <h1 class="title">{{ title }} <span class="secondary-text">Lineage</span></h1>
</template>

<script setup lang="ts">
interface Props {
  title: string
}

defineProps<Props>()
</script>

<style scoped>
.title {
  padding: 8px;
  background-color: var(--p-card-background);
  border-radius: 8px;
  box-shadow: var(--card-shadow);
  font-size: 14px;
}
.secondary-text {
  color: var(--p-text-muted-color);
}
</style>
