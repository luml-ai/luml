<template>
  <Button severity="secondary" @click="$emit('add')">
    <Plus :size="14" />
    <span>Add annotation</span>
  </Button>
</template>

<script setup lang="ts">
import { Button } from 'primevue'
import { Plus } from 'lucide-vue-next'

interface Emits {
  (event: 'add'): void
}

defineEmits<Emits>()
</script>

<style scoped></style>
