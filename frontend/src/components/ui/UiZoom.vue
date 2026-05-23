<template>
  <div class="zoom">
    <Button variant="text" severity="secondary" size="small" @click="emit('zoom-out')">
      <template #icon>
        <ZoomOut :size="14" />
      </template>
    </Button>
    <div class="zoom-value">
      <input v-model="modelValue" type="number" class="zoom-input" @input="changeZoom" />
      <span class="toolbar-zoom-value">%</span>
    </div>
    <Button variant="text" severity="secondary" size="small" @click="emit('zoom-in')">
      <template #icon>
        <ZoomIn :size="14" />
      </template>
    </Button>
  </div>
</template>

<script setup lang="ts">
import { Button } from 'primevue'
import { ZoomIn, ZoomOut } from 'lucide-vue-next'

interface Emits {
  (e: 'zoom-out'): void
  (e: 'zoom-in'): void
  (e: 'zoom-change', value: number): void
}

const emit = defineEmits<Emits>()

const modelValue = defineModel<string>('modelValue', { required: true })

function changeZoom(e: Event) {
  const target = e.target as HTMLInputElement
  const value = !isNaN(Number(target.value)) ? Number(target.value) / 100 : 0
  emit('zoom-change', value)
}
</script>

<style scoped>
.zoom {
  border-radius: 8px;
  border: 0.5px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  box-shadow: var(--card-shadow);
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
}
.zoom-value {
  font-size: 12px;
}
.zoom-input {
  width: auto;
  min-width: 0;
  border: none;
  outline: none;
  font-family: 'Inter', sans-serif;
  color: var(--p-text-color);
  display: inline-block;
  width: 23px;
  font-size: 12px;
}
</style>
