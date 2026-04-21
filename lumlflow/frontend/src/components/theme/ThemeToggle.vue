<template>
  <div class="custom-toggle" :class="{ dark: themeStore.theme === THEME.DARK }">
    <div class="custom-toggle-wrapper" @click="themeStore.toggleTheme">
      <div class="custom-toggle-item">
        <Sun :size="14" />
      </div>
      <div class="custom-toggle-item">
        <Moon :size="14" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useThemeStore } from '@/store/theme'
import { THEME } from '@/store/theme/theme.const'
import { Sun, Moon } from 'lucide-vue-next'

const themeStore = useThemeStore()
</script>

<style scoped>
.custom-toggle-wrapper {
  display: flex;
  gap: 6px;
  padding: 4px;
  border-radius: 16px;
  background-color: var(--p-button-secondary-background);
  cursor: pointer;
  position: relative;
}

.custom-toggle-wrapper::before {
  content: '';
  width: 20px;
  height: 20px;
  border-radius: 50%;
  position: absolute;
  top: 4px;
  right: 30px;
  background-color: var(--p-toggleswitch-handle-checked-background);
  transition: right 0.5s;
}

.dark .custom-toggle-wrapper::before {
  right: 4px;
}

.custom-toggle-item {
  width: 20px;
  height: 20px;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 50%;
  background-color: transparent;
  color: var(--p-toggleswitch-handle-color);
  position: relative;
  z-index: 2;
}

.custom-toggle-item:first-child {
  color: var(--p-toggleswitch-handle-checked-color);
}

.dark .custom-toggle-item:last-child {
  color: var(--p-toggleswitch-handle-color);
}

.dark .custom-toggle-item:first-child {
  color: var(--p-toggleswitch-handle-color);
}

.dark .custom-toggle-item:last-child {
  color: var(--p-toggleswitch-handle-checked-color);
}
</style>
