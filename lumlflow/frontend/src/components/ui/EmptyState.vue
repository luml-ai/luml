<template>
  <div class="flex flex-col items-center justify-center gap-3 py-20 text-muted-color">
    <component :is="icon" :size="40" stroke-width="1" />
    <span class="text-lg">{{ message }}</span>
  </div>
</template>

<script setup lang="ts">
import type { Component } from 'vue'

defineProps<{
  icon: Component
  message: string
}>()
</script>
