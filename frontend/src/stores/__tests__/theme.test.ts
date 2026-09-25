import { createPinia, setActivePinia } from 'pinia'
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

  it('keeps an authenticated user preference when the OS theme changes', () => {
    useAuthStore().isAuth = true
    localStorage.setItem('theme', 'light')
    const store = useThemeStore()
    store.checkTheme()

    dispatchThemeChange(true)
    expect(store.getCurrentTheme).toBe('light')

    localStorage.removeItem('theme')
    dispatchThemeChange(false)
    dispatchThemeChange(true)
    expect(store.getCurrentTheme).toBe('dark')
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
