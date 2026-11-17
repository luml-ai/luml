import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, markRaw, ref } from 'vue'
import PrimeVue from 'primevue/config'
import DynamicMetrics from '../DynamicMetrics.vue'
import DynamicMetricsItem from '../DynamicMetricsItem.vue'
import { ThemeKey } from '@/lib/theme/ThemeProvider'
import { MetricBucketStore } from '@/metric-buckets/MetricBucketStore'
import { useEvalsStore } from '@/store/evals'
import { useDynamicMetricsStore } from '@/store/dynamic-metrics'
import { plotlyService } from '@/services/PlotlyService'
import { FakeBucketSource, points, type ExperimentPoints } from './helpers/fakeBucketSource'
import { createPlotlyMock, installIntersectionObserver, settle } from './helpers/plotlyMock'

vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: vi.fn() }),
}))

const plotlyMock = vi.hoisted(() => ({ current: null as unknown }))

vi.mock('@/services/PlotlyService', () => ({
  plotlyService: { getPlotly: vi.fn(async () => plotlyMock.current), preload: vi.fn() },
}))

const ContentStub = defineComponent({
  props: { title: String, loading: Boolean, aggregationSteps: { type: Number, default: null } },
  template: '<div><slot /></div>',
})

let mock: ReturnType<typeof createPlotlyMock>
let viewport: ReturnType<typeof installIntersectionObserver>
let wrapper: VueWrapper | null = null
let theme = ref('light')

beforeEach(() => {
  setActivePinia(createPinia())
  mock = createPlotlyMock()
  plotlyMock.current = mock.plotly
  viewport = installIntersectionObserver()
  theme = ref('light')
  vi.stubGlobal(
    'ResizeObserver',
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  )
})

afterEach(() => {
  wrapper?.unmount()
  wrapper = null
  vi.unstubAllGlobals()
})

function metrics(count: number): ExperimentPoints {
  return Object.fromEntries(
    Array.from({ length: count }, (_, index) => [`metric_${index}`, points(0, 99)]),
  )
}

async function mountMetrics(
  data: Record<string, ExperimentPoints>,
  prepare: (source: FakeBucketSource) => void = () => {},
) {
  const source = new FakeBucketSource(data)
  prepare(source)
  const evalsStore = useEvalsStore()
  evalsStore.metricBucketStore = markRaw(new MetricBucketStore(source, { debounceMs: 0 }))
  wrapper = mount(DynamicMetrics, {
    props: {
      modelsInfo: { m1: { name: 'A', color: '#111111' }, m2: { name: 'B', color: '#222222' } },
    },
    global: {
      plugins: [[PrimeVue, { unstyled: true }]],
      provide: { [ThemeKey]: theme },
      stubs: { DynamicMetricsItemContent: ContentStub, ProgressSpinner: true },
    },
  })
  await settle()
  return { wrapper, source, store: useDynamicMetricsStore() }
}

function plots(view: VueWrapper): Element[] {
  return view.findAll('[data-testid="metric-plot"]').map((plot) => plot.element)
}

function chartNames(view: VueWrapper): string[] {
  return view.findAllComponents(DynamicMetricsItem).map((item) => item.props('metricName'))
}

describe('DynamicMetrics lazy charts', () => {
  it('reads only the charts in view and nothing again when paging back', async () => {
    const { wrapper: view, source, store } = await mountMetrics({ m1: metrics(60) })
    expect(plots(view)).toHaveLength(50)
    expect(source.bucketCalls).toHaveLength(0)
    expect(mock.calls).toHaveLength(0)

    plots(view)
      .slice(0, 6)
      .forEach((plot) => viewport.setVisible(plot, true))
    await settle()
    // The six charts that came into view together share one read.
    expect(source.bucketCalls.map((call) => call.keys)).toEqual([
      ['metric_0', 'metric_1', 'metric_2', 'metric_3', 'metric_4', 'metric_5'],
    ])

    store.setPage(1)
    await settle()
    expect(plots(view)).toHaveLength(10)
    viewport.setVisible(plots(view)[0] as Element, true)
    await settle()
    expect(source.bucketCalls).toHaveLength(2)

    store.setPage(0)
    await settle()
    plots(view)
      .slice(0, 6)
      .forEach((plot) => viewport.setVisible(plot, true))
    await settle()
    expect(source.bucketCalls).toHaveLength(2)
    expect(mock.lastCall(plots(view)[5] as HTMLElement).traces.length).toBeGreaterThan(0)
  })

  it('redraws only the charts that were drawn when the theme changes', async () => {
    const { wrapper: view } = await mountMetrics({ m1: metrics(10) })
    plots(view)
      .slice(0, 4)
      .forEach((plot) => viewport.setVisible(plot, true))
    await settle()
    const drawnBefore = new Set(mock.calls.map((call) => call.element))
    expect(drawnBefore.size).toBe(4)

    theme.value = 'dark'
    await settle()

    expect(new Set(mock.calls.map((call) => call.element))).toEqual(drawnBefore)
  })

  it('closes the subscription of a chart scrolled out of view', async () => {
    const { wrapper: view, source } = await mountMetrics({ m1: metrics(2) })
    source.hold()
    const [first] = plots(view) as [Element]
    viewport.setVisible(first, true)
    await settle()
    viewport.setVisible(first, false)
    await settle()
    source.releaseAll()
    await settle()

    expect(source.abortedCalls).toBe(1)
  })

  it('survives rapid page changes', async () => {
    const { wrapper: view, source, store } = await mountMetrics({ m1: metrics(160) })
    source.hold()
    for (const page of [1, 2, 0, 3, 1]) {
      store.setPage(page)
      await settle()
      plots(view)
        .slice(0, 2)
        .forEach((plot) => viewport.setVisible(plot, true))
      await settle()
    }
    source.releaseAll()
    await settle()

    expect(chartNames(view)[0]).toBe('metric_50')
    // Every page left behind aborted the one read its two charts shared; the last one is drawn.
    expect(source.abortedCalls).toBe(4)
    const [first] = plots(view) as [HTMLElement]
    expect(mock.lastCall(first).traces.length).toBeGreaterThan(0)
  })
})

describe('DynamicMetrics Plotly preload', () => {
  it('starts loading Plotly once when mounted, before any chart is in view', async () => {
    vi.mocked(plotlyService.preload).mockClear()
    vi.mocked(plotlyService.getPlotly).mockClear()
    await mountMetrics({ m1: metrics(3) })

    expect(plotlyService.preload).toHaveBeenCalledOnce()
    expect(plotlyService.getPlotly).not.toHaveBeenCalled()
  })
})

describe('DynamicMetrics names', () => {
  it('lists a key shared by several experiments once', async () => {
    const { wrapper: view } = await mountMetrics({
      m1: { loss: points(0, 9), acc: points(0, 9) },
      m2: { loss: points(0, 99) },
    })

    expect(chartNames(view)).toEqual(['acc', 'loss'])
    const loss = view.findAllComponents(DynamicMetricsItem)[1]
    expect(loss?.props('fullRange')).toEqual({ first: 0, last: 99 })
    expect(loss?.props('modelIds')).toEqual(['m1', 'm2'])
  })

  it('filters names case-insensitively before paging', async () => {
    const data = metrics(120)
    data['Train/LOSS'] = points(0, 9)
    const { wrapper: view, store } = await mountMetrics({ m1: data })
    store.setPage(2)
    await settle()

    await view.get('input').setValue('loss')
    await settle()

    expect(store.page).toBe(0)
    expect(chartNames(view)).toEqual(['Train/LOSS'])
    expect(view.get('input').attributes('placeholder')).toBe('Filter metrics')

    await view.get('input').setValue('nothing-like-this')
    await settle()
    expect(chartNames(view)).toEqual([])
    expect(view.text()).toContain('No metrics match the filter.')
  })

  it('reports an experiment whose catalog failed in its status, as it is not charted', async () => {
    const { store } = await mountMetrics({ m1: metrics(1), m2: metrics(1) }, (source) =>
      source.catalogErrors.add('m2'),
    )
    expect(store.modelIds).toEqual(['m1'])
    expect(store.statuses.map((status) => [status.modelId, status.error?.code ?? null])).toEqual([
      ['m1', null],
      ['m2', 'needs-newer-reader'],
    ])
  })

  it('shows nothing for an empty catalog', async () => {
    const { wrapper: view } = await mountMetrics({ m1: {} })
    expect(view.findAllComponents(DynamicMetricsItem)).toHaveLength(0)
    expect(view.find('input').exists()).toBe(false)
  })
})

describe('DynamicMetrics refresh', () => {
  it('re-reads the catalog of the experiment and redraws the grown metric', async () => {
    const { wrapper: view, source, store } = await mountMetrics({ m1: { loss: points(0, 9) } })
    const [plot] = plots(view) as [HTMLElement]
    viewport.setVisible(plot, true)
    await settle()
    expect(mock.lastCall(plot).traces[0]?.x).toHaveLength(10)

    source.data.m1 = { loss: points(0, 19) }
    await store.refresh(['m1'])
    await settle()

    expect(source.getMetricCatalogs).toHaveBeenLastCalledWith(
      { modelIds: ['m1'], refresh: true },
      expect.any(AbortSignal),
    )
    expect(view.findComponent(DynamicMetricsItem).props('fullRange')).toEqual({
      first: 0,
      last: 19,
    })
    expect(mock.lastCall(plot).traces[0]?.x).toHaveLength(20)
  })
})
