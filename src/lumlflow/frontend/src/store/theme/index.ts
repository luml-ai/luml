import type { ThemeType } from './theme.interface'
import { defineStore } from 'pinia'
import { THEME } from './theme.const'
import { useLocalStorage } from '@vueuse/core'
import { watch } from 'vue'

export const useThemeStore = defineStore('theme', () => {
  const theme = useLocalStorage<ThemeType>('theme', THEME.LIGHT)

  function toggleTheme() {
    theme.value = theme.value === THEME.LIGHT ? THEME.DARK : THEME.LIGHT
  }

  watch(
    theme,
    (newTheme) => {
      document.documentElement.setAttribute('data-theme', newTheme)
    },
    { immediate: true },
  )

  return {
    theme,
    toggleTheme,
  }
})
