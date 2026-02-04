<template>
  <header class="flex items-center justify-between px-4 py-2 bg-primary">
    <router-link to="/">Logo</router-link>
    <div class="flex items-center gap-2">
      <Button @click="themeStore.toggleTheme">
        <template #icon>
          <component
            :is="themeStore.theme === THEME.LIGHT ? Sun : Moon"
            :size="18"
            stroke-width="1.5"
          />
        </template>
      </Button>
      <Button>GitHub</Button>
      <Button>Docs</Button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { useThemeStore } from '@/store/theme'
import { THEME } from '@/store/theme/theme.const'
import { Sun, Moon } from 'lucide-vue-next'
import Button from 'primevue/button'

const themeStore = useThemeStore()
</script>

<style scoped></style>
