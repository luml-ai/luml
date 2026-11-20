import { afterEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import {
  Compare,
  SectionState,
  Severity,
  Window,
  type AlertBanner,
  type MultivariatePanel,
  type RuntimeResponse,
} from '@/api/monitoring/interfaces'
import { useFiltersStore } from '@/store/filters'
import { getOpenAlerts } from '@/utils/alerts'
import { escapeChartLabel } from '@/utils/charts'
import { copyToClipboard } from '@/utils/clipboard'
import { countPsiAttention, getMultivariateMetrics } from '@/utils/drift'
import { getRuntimeCards } from '@/utils/runtime'
import { formatCardDelta } from '@/utils/cards'
import { isRecordingOff } from '@/utils/worker'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('filters store', () => {
  it('keeps the selected snapshot window alongside custom dates', () => {
    setActivePinia(createPinia())
    const store = useFiltersStore()
    store.setWindow(Window.D7)
    store.enableCustomMode()
    store.setCustomRange(new Date('2026-11-01T00:00:00Z'), new Date('2026-11-08T00:00:00Z'))
    expect(store.dimensions.window).toBe(Window.D7)
    expect(store.dimensions.start).toBe('2026-11-01T00:00:00.000Z')
    expect(store.dimensions.end).toBe('2026-11-08T00:00:00.000Z')
  })
})

describe('alerts', () => {
  it('drops acknowledged alerts from section banners', () => {
    const alert = (metric: string, state?: string): AlertBanner => ({
      group: 'runtime',
      metric,
      severity: Severity.WARNING,
      message: metric,
      state,
    })
    const open = getOpenAlerts([alert('a'), alert('b', 'acknowledged'), alert('c', 'open')])
    expect(open.map((item) => item.metric)).toEqual(['a', 'c'])
  })
})

describe('chart labels', () => {
  it('escapes markup before ApexCharts renders it as HTML', () => {
    const payload = '<img src=x onerror="alert(1)"> & \'x\''
    const escaped = escapeChartLabel(payload)
    expect(escaped).toBe('&lt;img src=x onerror=&quot;alert(1)&quot;&gt; &amp; &#39;x&#39;')
    const container = document.createElement('div')
    container.innerHTML = escaped
    expect(container.childElementCount).toBe(0)
    expect(container.textContent).toBe(payload)
  })
})

describe('multivariate drift', () => {
  it('counts only features at or above the PSI attention threshold', () => {
    const panel = {
      state: SectionState.OK,
      status: Severity.OK,
      explained_variance: [],
      reference_projection: [],
      current_projection: [],
      feature_psi: [0.05, 0.19, 0.2, 0.4].map((psi, index) => ({
        feature: `f${index}`,
        psi,
        severity: Severity.OK,
      })),
    } satisfies MultivariatePanel
    expect(countPsiAttention(panel)).toBe(2)
    const metric = getMultivariateMetrics(panel).find((item) => item.label === 'Per-feature PSI')
    expect(metric?.value).toBe('2 / 4')
  })
})

describe('runtime cards', () => {
  const runtime = {
    state: SectionState.OK,
    request_count: 100,
    error_rate: 0.1,
    baseline: { request_count: 80, error_rate: 0.05 },
  } as unknown as RuntimeResponse

  it('renders comparison deltas when a baseline is present', () => {
    const cards = getRuntimeCards(runtime, Compare.PREVIOUS)
    const deltaFor = (key: string) => {
      const card = cards.find((item) => item.key === key)
      return card ? formatCardDelta(card) : null
    }
    expect(deltaFor('request_count')).toBe('↑ 20 vs previous period')
    expect(deltaFor('error_rate')).toBe('↑ 5.0pp vs previous period')
  })

  it('omits deltas when compare is off', () => {
    const cards = getRuntimeCards(runtime, Compare.OFF)
    expect(cards.every((card) => card.delta == null)).toBe(true)
  })
})

describe('clipboard', () => {
  it('falls back to a selection copy when the async clipboard is denied', async () => {
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn().mockRejectedValue(new Error('denied')) },
    })
    const execCommand = vi.fn().mockReturnValue(true)
    Object.defineProperty(document, 'execCommand', { configurable: true, value: execCommand })
    await copyToClipboard('request-1')
    expect(execCommand).toHaveBeenCalledWith('copy')
  })

  it('rejects when neither copy path succeeds', async () => {
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: undefined })
    Object.defineProperty(document, 'execCommand', {
      configurable: true,
      value: vi.fn().mockReturnValue(false),
    })
    await expect(copyToClipboard('request-1')).rejects.toThrow()
  })
})

describe('worker health', () => {
  it('flags recording that is not running', () => {
    expect(isRecordingOff(null)).toBe(false)
    const health = (state: 'recording' | 'fault') =>
      ({ recording: { state, reason: null } }) as never
    expect(isRecordingOff(health('recording'))).toBe(false)
    expect(isRecordingOff(health('fault'))).toBe(true)
  })
})
