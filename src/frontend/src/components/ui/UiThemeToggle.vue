<template>
  <div class="custom-toggle" :class="{ dark: modelValue === 'dark' }">
    <button
      v-if="iconOnly"
      type="button"
      class="custom-toggle-wrapper custom-toggle-wrapper--icon-only"
      @click="click"
    >
      <div class="custom-toggle-item" :class="{ active: modelValue === 'light' }">
        <sun :size="14" />
      </div>
      <div class="custom-toggle-item" :class="{ active: modelValue === 'dark' }">
        <moon :size="14" />
      </div>
    </button>

    <button v-else type="button" class="custom-toggle-wrapper" @click="click">
      <div class="custom-toggle-item" :class="{ active: modelValue === 'light' }">
        <sun :size="14" />
        <span class="custom-toggle-item-text">Light</span>
      </div>
      <div class="custom-toggle-item" :class="{ active: modelValue === 'dark' }">
        <span class="custom-toggle-item-text">Dark</span>
        <moon :size="14" />
      </div>
    </button>
  </div>
</template>

<script setup lang="ts">
import type { Theme } from '@/stores/theme'
import { Sun, Moon } from 'lucide-vue-next'

type Props = {
  modelValue: Theme
  iconOnly: boolean
}

type Emits = {
  'update:modelValue': [Theme]
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

function click() {
  const newTheme: Theme = props.modelValue === 'dark' ? 'light' : 'dark'
  emit('update:modelValue', newTheme)
}
</script>

<style scoped>
.custom-toggle-wrapper {
  display: flex;
  gap: 6px;
  padding: 4px;
  border-radius: 16px;
  background-color: var(--p-toggleswitch-background);
  cursor: pointer;
  position: relative;
  overflow: hidden;
  width: 148px;
}

.custom-toggle-wrapper--icon-only {
  padding: 4px;
  border-radius: 50%;
  width: 32px;
  height: 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.custom-toggle-wrapper::before {
  content: '';
  border-radius: 14px;
  position: absolute;
  top: 4px;
  bottom: 4px;
  background-color: var(--p-toggleswitch-handle-checked-background);
  width: 66px;
  right: 77px;
  transition:
    right 0.5s,
    width 0.5s;
}

.dark .custom-toggle-wrapper::before {
  right: 4px;
  width: 75px;
}

.custom-toggle-wrapper--icon-only::before {
  display: none;
}

.custom-toggle-item {
  padding: 4px;
  display: flex;
  justify-content: center;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border-radius: 14px;
  background-color: transparent;
  color: var(--p-toggleswitch-handle-color);
  position: relative;
  z-index: 2;
}

.custom-toggle-wrapper--icon-only .custom-toggle-item {
  width: 24px;
  height: 24px;
  flex: 0 0 auto;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 50%;
  background-color: var(--p-toggleswitch-handle-checked-background);
  transition: transform 0.5s;
}

.dark .custom-toggle-wrapper--icon-only .custom-toggle-item {
  transform: translateY(-30px);
}

.custom-toggle-item.active {
  color: var(--p-menu-item-color);
}

.custom-toggle-item-text {
  font-weight: 500;
  font-size: 14px;
}
</style>
