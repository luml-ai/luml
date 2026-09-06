<template>
  <div class="wrapper">
    <NotebookCell v-for="i in 10" :key="i" class="not-last:mb-2" />
  </div>
</template>

<script setup lang="ts">
import NotebookCell from '@/components/notebooks/cell/NotebookCell.vue'
</script>

<style scoped>
.wrapper {
  height: calc(100vh - 211px);
  overflow-y: auto;
  margin-bottom: -20px;
}
</style>
