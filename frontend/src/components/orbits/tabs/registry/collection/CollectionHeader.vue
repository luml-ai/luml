<template>
  <header class="header">
    <h3 class="title">
      {{ title }}
      <UiId :id="id" variant="button"></UiId>
    </h3>
    <div class="buttons">
      <Button @click="$emit('add')">
        <Plus :size="14" />
        <span>Add model</span>
      </Button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { Button } from 'primevue'
import { Plus } from 'lucide-vue-next'
import UiId from '@/components/ui/UiId.vue'

type Props = {
  title: string
  addAvailable: boolean
  id: string
}

type Emits = {
  add: []
}

defineProps<Props>()
defineEmits<Emits>()
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.buttons {
  display: flex;
  gap: 8px;
}

.title {
  display: flex;
  align-items: center;
  gap: 12px;
}
</style>
