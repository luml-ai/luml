export type Theme = 'light' | 'dark'

export const THEME_MESSAGE_TYPE = 'monitoring:theme'

const THEME_STORAGE_KEY = 'monitoring-theme'

function isTheme(value: unknown): value is Theme {
  return value === 'light' || value === 'dark'
}

function readStoredTheme(): string | null {
  try {
    return sessionStorage.getItem(THEME_STORAGE_KEY)
  } catch {
    return null
  }
}

export function applyTheme(next: Theme): void {
  document.documentElement.dataset.theme = next
  try {
    sessionStorage.setItem(THEME_STORAGE_KEY, next)
  } catch {
    return
  }
}

export function initTheme(): void {
  const fromQuery = new URLSearchParams(window.location.search).get('theme')
  const stored = readStoredTheme()
  applyTheme(isTheme(fromQuery) ? fromQuery : isTheme(stored) ? stored : 'light')

  window.addEventListener('message', (event: MessageEvent) => {
    if (event.source !== window.parent) return
    const data = event.data as { type?: string; theme?: unknown } | null
    if (data?.type === THEME_MESSAGE_TYPE && isTheme(data.theme)) {
      applyTheme(data.theme)
    }
  })
}
