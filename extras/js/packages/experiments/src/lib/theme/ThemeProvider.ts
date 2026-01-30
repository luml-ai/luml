import { provide, inject, ref, type Ref } from 'vue'

export const ThemeKey = Symbol('experiments-theme')

export function provideTheme(theme: Ref<'light' | 'dark'>) {
  const state = ref(theme)
  provide(ThemeKey, state)
  return state
}

export function useTheme() {
  const theme = inject(ThemeKey)
  if (!theme) throw new Error('Theme not provided!')
  return theme
}
