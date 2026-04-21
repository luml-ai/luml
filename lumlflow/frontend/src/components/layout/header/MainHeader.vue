<template>
  <header
    class="flex items-center justify-between px-4 py-3 bg-(--p-content-hover-background) border-b border-(--p-divider-border-color)"
  >
    <router-link to="/">
      <img :src="currentLogo" alt="Logo" class="w-[175px] h-7" />
    </router-link>
    <div class="flex items-center gap-4">
      <div class="flex items-center gap-2">
        <Button
          class="p-2! text-color! hover:text-muted-color! hover:bg-transparent! active:bg-transparent!"
          variant="text"
        >
          <Github :size="14" />
          GitHub
        </Button>
        <Button
          class="p-2! text-color! hover:text-muted-color! hover:bg-transparent! active:bg-transparent!"
          variant="text"
        >
          <File :size="14" />
          Docs
        </Button>
      </div>
      <ThemeToggle />
      <ApiKeyButton />
    </div>
  </header>
</template>

<script setup lang="ts">
import { Github, File } from 'lucide-vue-next'
import Button from 'primevue/button'
import logo from '@/assets/img/logo.svg'
import logoDark from '@/assets/img/logo-dark.svg'
import ApiKeyButton from './ApiKeyButton.vue'
import ThemeToggle from '@/components/theme/ThemeToggle.vue'
import { useThemeStore } from '@/store/theme'
import { THEME } from '@/store/theme/theme.const'
import { computed } from 'vue'

const themeStore = useThemeStore()

const currentLogo = computed(() => {
  return themeStore.theme === THEME.DARK ? logo : logoDark
})
</script>

<style scoped></style>
