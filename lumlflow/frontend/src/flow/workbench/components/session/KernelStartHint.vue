<template>
  <span
    v-tooltip.top="'Previews never need a kernel'"
    class="inline-flex items-center gap-1 text-sm text-muted-color"
  >
    <Zap :size="14" class="shrink-0" />
    this starts the kernel
  </span>
</template>

<script setup lang="ts">
import { Zap } from 'lucide-vue-next'

</script>
