<template>
  <div class="workspace-flow-page">
    <NotebookHeader class="mb-2" />
    <div class="grid grid-cols-[292px_1fr] gap-2">
      <NotebooksSidebar />
      <div>
        <NotebookToolbar class="mb-2" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import NotebookHeader from '@/components/notebooks/NotebookHeader.vue'
import NotebooksSidebar from '@/components/notebooks/NotebooksSidebar.vue'
import NotebookToolbar from '@/components/notebooks/NotebookToolbar.vue'

const route = useRoute()

const directory = computed(() => route.query.directory)
</script>

<style scoped></style>
