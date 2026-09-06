<template>
  <div class="toolbar">
    <div class="toolbar-left">
      <Button variant="text">
        <Plus :size="14" />
        New cell
      </Button>
      <Button variant="text" severity="secondary">
        <Terminal :size="14" />
        Scratch
      </Button>
    </div>
    <div class="toolbar-right">
      <Button variant="text" severity="danger">
        <Pause :size="14" />
        Stop session
      </Button>
      <Button variant="text">
        <Play :size="14" />
        Rerun lane
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Pause, Play, Plus, Terminal } from 'lucide-vue-next'
import { Button } from 'primevue'
</script>

<style scoped>
@reference "@/assets/css/index.css";

.toolbar {
  @apply flex items-center justify-between gap-2;
}

.toolbar-left {
  @apply flex items-center gap-2;
}

.toolbar-right {
  @apply flex items-center gap-4;
}
</style>
