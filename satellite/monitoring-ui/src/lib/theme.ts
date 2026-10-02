import { computed, ref } from 'vue'

export type Theme = 'light' | 'dark'

/** Message the Platform posts into the iframe when its theme toggles. */
export const THEME_MESSAGE_TYPE = 'monitoring:theme'

export const theme = ref<Theme>('light')

export function applyTheme(next: Theme): void {
  theme.value = next
  document.documentElement.dataset.theme = next
  try {
    sessionStorage.setItem('monitoring-theme', next)
  } catch {
    // storage can be unavailable in strict embeds; the query/message still win
  }
}

function isTheme(value: unknown): value is Theme {
  return value === 'light' || value === 'dark'
}

/**
 * Pick up the Platform's theme and follow it live.
 *
 * The first paint reads the `?theme=` the launch redirect carried through (with a
 * sessionStorage echo as fallback for in-app reloads that lose the query). After
 * that the Platform pushes changes with postMessage; only messages from the parent
 * frame are honored — the payload is cosmetic, but there is no reason to listen to
 * anyone else.
 */
export function initTheme(): void {
  const fromQuery = new URLSearchParams(window.location.search).get('theme')
  let stored: string | null = null
  try {
    stored = sessionStorage.getItem('monitoring-theme')
  } catch {
    stored = null
  }
  const initial = isTheme(fromQuery) ? fromQuery : isTheme(stored) ? stored : 'light'
  applyTheme(initial)

  window.addEventListener('message', (event: MessageEvent) => {
    if (event.source !== window.parent) return
    const data = event.data as { type?: string; theme?: unknown } | null
    if (data?.type === THEME_MESSAGE_TYPE && isTheme(data.theme)) {
      applyTheme(data.theme)
    }
  })
}

// apexcharts needs literal colors; resolve the same tokens the dashboard uses
export function chartColor(value: string): string {
  const token = /^var\((--luml-[\w-]+)\)$/.exec(value)
  if (!token) return value
  return chartColor(getComputedStyle(document.documentElement).getPropertyValue(token[1]).trim())
}

export const chartGridColor = computed(() => {
  theme.value
  return chartColor('var(--luml-border)')
})
export const chartTextColor = computed(() => {
  theme.value
  return chartColor('var(--luml-fg-muted)')
})
export const chartSeriesColors = computed(() => {
  theme.value
  return Array.from({ length: 14 }, (_, index) => chartColor(`var(--luml-chart-${index + 1})`))
})
export const chartTooltipTheme = computed(() => theme.value)
