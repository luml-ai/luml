<template>
  <div class="pointers">
    <Button
      class="small-button"
      variant="text"
      :severity="modelValue === 'hand' ? 'primary' : 'secondary'"
      size="small"
      @click="modelValue = 'hand'"
    >
      <template #icon>
        <Pointer :size="14" />
      </template>
    </Button>
    <Button
      class="small-button"
      variant="text"
      :severity="modelValue === 'pointer' ? 'primary' : 'secondary'"
      size="small"
      @click="modelValue = 'pointer'"
    >
      <template #icon>
        <MousePointer2 :size="14" />
      </template>
    </Button>
  </div>
</template>

<script setup lang="ts">
import { MousePointer2, Pointer } from 'lucide-vue-next'
import { Button } from 'primevue'

const modelValue = defineModel<'pointer' | 'hand'>('modelValue', { required: true })
</script>

<style scoped>
.pointers {
  display: flex;
  align-items: center;
  gap: 6px;
}
.small-button {
  padding: 4px;
  width: auto;
  height: auto;
}
</style>
