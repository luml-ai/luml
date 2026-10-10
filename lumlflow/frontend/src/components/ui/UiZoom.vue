<template>
  <div class="zoom" :class="`zoom-${align}`">
    <Button variant="text" severity="secondary" size="small" class="p-0!" @click="emit('zoomOut')">
      <template #icon>
        <ZoomOut :size="14" />
      </template>
    </Button>
    <div class="zoom-value">
      <input v-model="modelValue" type="number" class="zoom-input" @input="changeZoom" />
      <span>%</span>
    </div>
    <Button variant="text" severity="secondary" size="small" class="p-0!" @click="emit('zoomIn')">
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
  zoomOut: []
  zoomIn: []
  zoomChange: [value: number]
}

interface Props {
  align?: 'horizontal' | 'vertical'
}

withDefaults(defineProps<Props>(), {
  align: 'horizontal',
})

const emit = defineEmits<Emits>()

const modelValue = defineModel<string>('modelValue', { required: true })

function changeZoom(e: Event) {
  const target = e.target as HTMLInputElement
  const value = !isNaN(Number(target.value)) ? Number(target.value) / 100 : 0
  emit('zoomChange', value)
}
</script>

<style scoped>
.zoom {
  border-radius: 8px;
  border: 0.5px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  box-shadow: var(--p-card-shadow);
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
}
.zoom-vertical {
  flex-direction: column;
  align-items: center;
}
.zoom-value {
  font-size: 12px;
}
.zoom-vertical .zoom-value {
  font-size: 10px;
}
.zoom-vertical .zoom-value input {
  font-size: inherit;
  text-align: right;
}
.zoom-input {
  min-width: 0;
  border: none;
  outline: none;
  font-family: 'Inter', sans-serif;
  color: var(--p-text-color);
  display: inline-block;
  width: 23px;
  font-size: 12px;
}
input[type='number']::-webkit-inner-spin-button,
input[type='number']::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
input[type='number'] {
  -moz-appearance: textfield;
}
</style>
