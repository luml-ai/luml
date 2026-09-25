import { defineStore, storeToRefs } from 'pinia'
import { computed, onScopeDispose, ref, watch } from 'vue'
import { useAuthStore } from './auth'

export type Theme = 'light' | 'dark'

export const useThemeStore = defineStore('theme', () => {
  const authStore = useAuthStore()
  const { isAuth } = storeToRefs(authStore)

  const theme = ref<Theme>('light')
  const darkModeQuery = window.matchMedia('(prefers-color-scheme: dark)')

  const syncSystemTheme = (event: MediaQueryListEvent) => {
    if (!localStorage.getItem('theme') || !isAuth.value) {
      theme.value = event.matches ? 'dark' : 'light'
    }
  }

  darkModeQuery.addEventListener('change', syncSystemTheme)
  onScopeDispose(() => darkModeQuery.removeEventListener('change', syncSystemTheme))

  const getCurrentTheme = computed(() => theme.value)

  const toggleTheme = () => {
    theme.value = theme.value === 'light' ? 'dark' : 'light'
  }

  const changeTheme = () => {
    toggleTheme()

    localStorage.setItem('theme', theme.value)
  }

  const checkTheme = () => {
    const themeInLocalstorage = localStorage.getItem('theme')

    if (themeInLocalstorage && isAuth.value) {
      theme.value = themeInLocalstorage as Theme
    } else {
      theme.value = darkModeQuery.matches ? 'dark' : 'light'
    }
  }

  watch(theme, () => {
    document.documentElement.dataset.theme = theme.value
  })

  watch(isAuth, checkTheme)

  return { getCurrentTheme, changeTheme, checkTheme }
})
