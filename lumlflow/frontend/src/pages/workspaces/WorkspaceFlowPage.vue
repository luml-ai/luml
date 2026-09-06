<template>
  <div class="workspace-flow-page">
    <NotebookToolbar class="mb-2"/>
    <div class="grid grid-cols-[292px_1fr] gap-2">
      <NotebooksSidebar />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import NotebookToolbar from '@/components/notebooks/NotebookToolbar.vue'
import NotebooksSidebar from '@/components/notebooks/NotebooksSidebar.vue'

const route = useRoute()

const directory = computed(() => route.query.directory)
</script>

<style scoped></style>
