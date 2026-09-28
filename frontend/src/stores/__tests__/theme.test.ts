import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../auth', async () => {
  const { defineStore } = await import('pinia')
  const { ref } = await import('vue')
  return { useAuthStore: defineStore('auth', () => ({ isAuth: ref(false) })) }
})

import { useAuthStore } from '../auth'
import { useThemeStore } from '../theme'

describe('theme store', () => {
  let mediaQuery: MediaQueryList
  let dispatchThemeChange: (matches: boolean) => void

  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()

    const listeners = new Set<(event: MediaQueryListEvent) => void>()
    mediaQuery = {
      matches: false,
      media: '(prefers-color-scheme: dark)',
      addEventListener: vi.fn((_type: string, listener: EventListenerOrEventListenerObject) => {
        listeners.add(listener as (event: MediaQueryListEvent) => void)
      }),
      removeEventListener: vi.fn((_type: string, listener: EventListenerOrEventListenerObject) => {
        listeners.delete(listener as (event: MediaQueryListEvent) => void)
      }),
    } as unknown as MediaQueryList
    dispatchThemeChange = (matches) => {
      Object.defineProperty(mediaQuery, 'matches', { configurable: true, value: matches })
      listeners.forEach((listener) => listener({ matches } as MediaQueryListEvent))
    }
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => mediaQuery),
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('follows every OS theme change after repeated checks', () => {
    const store = useThemeStore()
    store.checkTheme()
    store.checkTheme()
    expect(store.getCurrentTheme).toBe('light')
    expect(mediaQuery.addEventListener).toHaveBeenCalledTimes(1)

    dispatchThemeChange(true)
    expect(store.getCurrentTheme).toBe('dark')
    dispatchThemeChange(false)
    expect(store.getCurrentTheme).toBe('light')
    dispatchThemeChange(true)
    expect(store.getCurrentTheme).toBe('dark')
  })

  it('keeps an authenticated user preference when the OS theme changes', async () => {
    const authStore = useAuthStore()
    authStore.isAuth = true
    localStorage.setItem('theme', 'light')
    const store = useThemeStore()
    store.checkTheme()

    dispatchThemeChange(true)
    expect(store.getCurrentTheme).toBe('light')

    authStore.isAuth = false
    await nextTick()
    expect(store.getCurrentTheme).toBe('dark')
    dispatchThemeChange(false)
    expect(store.getCurrentTheme).toBe('light')
  })

  it('keeps a theme chosen while logged out when the OS theme changes', () => {
    const store = useThemeStore()
    store.checkTheme()
    store.changeTheme()
    expect(store.getCurrentTheme).toBe('dark')

    dispatchThemeChange(true)
    dispatchThemeChange(false)
    expect(store.getCurrentTheme).toBe('dark')
  })

  it('follows the OS for a logged out user with a previously saved theme', () => {
    localStorage.setItem('theme', 'dark')
    const store = useThemeStore()
    store.checkTheme()
    expect(store.getCurrentTheme).toBe('light')

    dispatchThemeChange(true)
    expect(store.getCurrentTheme).toBe('dark')
    dispatchThemeChange(false)
    expect(store.getCurrentTheme).toBe('light')
  })

  it('removes the OS listener when the store is disposed', () => {
    const store = useThemeStore()
    store.checkTheme()
    store.$dispose()

    expect(mediaQuery.removeEventListener).toHaveBeenCalledTimes(1)
    dispatchThemeChange(true)
    expect(store.getCurrentTheme).toBe('light')
  })
})
