import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { defineComponent, ref } from 'vue'
import { CircleAlert } from 'lucide-vue-next'
import DynamicMetricsItem from '../DynamicMetricsItem.vue'
import MetricBucketPlot from '../MetricBucketPlot.vue'
import type { PlotStatus } from '../dynamic-metrics.interface'
import { plotlyService } from '@/services/PlotlyService'
import { ThemeKey } from '@/lib/theme/ThemeProvider'
import { MetricBucketStore } from '@/metric-buckets/MetricBucketStore'
import { BucketCache } from '@/metric-buckets/BucketCache'
import type { BucketReadRequest } from '@/metric-buckets/planner'
import type { ModelInfo } from '@/interfaces/interfaces'
import {
  hoverLabel,
  ISOLATED_MARKER_SIZE,
  type ScatterTrace,
  type StepRange,
} from '@/lib/metric-charts/bucketTraces'
import { FakeBucketSource, points, type ExperimentPoints } from './helpers/fakeBucketSource'
import { createPlotlyMock, settle } from './helpers/plotlyMock'

const plotlyMock = vi.hoisted(() => ({ current: null as unknown }))

vi.mock('@/services/PlotlyService', () => ({
  plotlyService: { getPlotly: vi.fn(async () => plotlyMock.current), preload: vi.fn() },
}))

const ContentStub = defineComponent({
  props: {
    title: String,
    loading: Boolean,
    aggregationSteps: { type: Number, default: null },
    error: { type: String, default: null },
  },
  data: () => ({ scaled: false }),
  template: '<div><slot /><slot v-if="scaled" name="scaled" /></div>',
})

const MODELS: Record<string, ModelInfo> = {
  m1: { name: 'Model A', color: '#112233' },
  m2: { name: 'Model B', color: '#445566' },
}

let mock: ReturnType<typeof createPlotlyMock>
let mounted: VueWrapper[] = []
let resizeCallbacks: ResizeObserverCallback[] = []

class ControllableResizeObserver {
  constructor(callback: ResizeObserverCallback) {
    resizeCallbacks.push(callback)
  }
  observe() {}
  unobserve() {}
  disconnect() {}
}

function setWidth(width: number) {
  Object.defineProperty(HTMLElement.prototype, 'clientWidth', {
    configurable: true,
    get: () => width,
  })
}

beforeEach(() => {
  mock = createPlotlyMock()
  plotlyMock.current = mock.plotly
  resizeCallbacks = []
  vi.stubGlobal('ResizeObserver', ControllableResizeObserver)
  setWidth(0)
})

afterEach(() => {
  mounted.forEach((wrapper) => wrapper.unmount())
  mounted = []
  vi.unstubAllGlobals()
})

function recordRequests(store: MetricBucketStore): BucketReadRequest[] {
  const requests: BucketReadRequest[] = []
  const subscribe = store.subscribe.bind(store)
  vi.spyOn(store, 'subscribe').mockImplementation((listener) => {
    const subscription = subscribe(listener)
    return {
      get state() {
        return subscription.state
      },
      request(request: BucketReadRequest) {
        requests.push(request)
        subscription.request(request)
      },
      close: () => subscription.close(),
    }
  })
  return requests
}

interface Setup {
  data: Record<string, ExperimentPoints>
  metric?: string
  fullRange: StepRange
  modelIds?: string[]
  cache?: BucketCache
  theme?: ReturnType<typeof ref<string>>
  legacy?: string[]
}

async function mountChart(setup: Setup) {
  const source = new FakeBucketSource(setup.data)
  for (const modelId of setup.legacy ?? []) source.legacy.add(modelId)
  const store = new MetricBucketStore(source, { debounceMs: 0, cache: setup.cache })
  const requests = recordRequests(store)
  const theme = setup.theme ?? ref('light')
  const wrapper = mount(DynamicMetricsItem, {
    props: {
      store,
      metricName: setup.metric ?? 'loss',
      modelIds: setup.modelIds ?? Object.keys(setup.data),
      fullRange: setup.fullRange,
      modelsInfo: MODELS,
    },
    global: {
      provide: { [ThemeKey]: theme },
      stubs: { DynamicMetricsItemContent: ContentStub, ProgressSpinner: true },
      directives: { tooltip: {} },
    },
  })
  mounted.push(wrapper)
  await settle()
  const element = wrapper.get('[data-testid="metric-plot"]').element as HTMLElement
  return { wrapper, source, store, requests, element, theme }
}

type Trace = Record<string, unknown> & { uid: string; x: number[]; y: (number | null)[] }

function traces(element?: HTMLElement): Trace[] {
  return mock.lastCall(element).traces as Trace[]
}

function lineOf(modelId: string, element?: HTMLElement): Trace {
  const line = traces(element).find((trace) => trace.uid === `${modelId}-line`)
  if (!line) throw new Error(`No line for ${modelId}`)
  return line
}

function xRange(element?: HTMLElement): unknown {
  return (mock.lastCall(element).layout.xaxis as Record<string, unknown>).range
}

const LONG: Record<string, ExperimentPoints> = {
  m1: { loss: points(0, 9999, (step) => step % 10) },
}

describe('DynamicMetricsItem rendering', () => {
  it('draws aggregated buckets as an average line over a min-max band in the model colour', async () => {
    const { element, wrapper } = await mountChart({
      data: LONG,
      fullRange: { first: 0, last: 9999 },
    })

    const drawn = traces(element)
    expect(drawn.map((trace) => trace.uid)).toEqual(['m1-band', 'm1-line'])
    const [band, line] = drawn as [Trace, Trace]
    // Level 4: 40 buckets of 256 steps, the last one holding steps 9984-9999; each spans its steps.
    const extents = Array.from({ length: 40 }, (_, index) => [
      index * 256,
      Math.min(index * 256 + 255, 9999),
    ])
    expect(band.x).toEqual([...extents.flat(), ...extents.flat().reverse()])
    expect(band.y).toEqual([...Array(80).fill(9), ...Array(80).fill(0)])
    expect(band.fill).toBe('toself')
    expect(band.fillcolor).toBe('rgba(17, 34, 51, 0.2)')
    expect(band.opacity).toBeUndefined()
    expect(band.hoverinfo).toBe('skip')
    expect((line.line as Record<string, unknown>).color).toBe('#112233')
    expect(line.y[0]).toBe((25 * 45 + 15) / 256)
    // Level 4 (256 steps per bucket) is the finest that fits 10,000 steps in 100 buckets.
    expect(line.x[0]).toBe(127.5)
    const text = hoverLabel(line as unknown as ScatterTrace, 0)
    expect(text).toContain('min 0 · max 9')
    expect(text).toContain('256 points · steps 0–255')
    expect(wrapper.findComponent(ContentStub).props('aggregationSteps')).toBe(256)
  })

  it('draws a legacy experiment whose catalog has no count, min or max', async () => {
    const current = await mountChart({ data: LONG, fullRange: { first: 0, last: 9999 } })
    const expected = traces(current.element)
    const legacy = await mountChart({
      data: LONG,
      fullRange: { first: 0, last: 9999 },
      legacy: ['m1'],
    })

    const [catalog] = await legacy.source.getMetricCatalogs()
    expect(catalog).toMatchObject({
      ok: true,
      value: { revision: 2, metrics: [{ key: 'loss', count: null, min: null, max: null }] },
    })
    expect(traces(legacy.element)).toEqual(expected)
    expect(legacy.wrapper.findComponent(ContentStub).props('aggregationSteps')).toBe(256)
  })

  it('puts stable test hooks on the card: key, displayed level and state', async () => {
    const { wrapper } = await mountChart({ data: LONG, fullRange: { first: 0, last: 9999 } })
    const card = wrapper.findComponent(ContentStub)
    expect(card.attributes()).toMatchObject({
      'data-testid': 'metric-chart',
      'data-metric-key': 'loss',
      'data-level': '4',
      'data-state': 'final',
    })
  })

  it('draws exact logged values without a band at level 0', async () => {
    const { element, wrapper } = await mountChart({
      data: { m1: { loss: points(1, 3, (step) => [0, 0.1 + 0.2, 10, 0][step] ?? null) } },
      fullRange: { first: 1, last: 3 },
    })

    const drawn = traces(element)
    expect(drawn).toHaveLength(1)
    const line = lineOf('m1', element)
    expect(line.x).toEqual([1, 2, 3])
    expect(line.y).toEqual([0.1 + 0.2, 10, 0])
    expect(line.mode).toBe('lines')
    expect((line.line as Record<string, unknown>).shape).toBe('linear')
    expect(hoverLabel(line as unknown as ScatterTrace, 0)).toBe(
      '<b>Model A</b>: 0.30000000000000004 · step 1',
    )
    expect(wrapper.findComponent(ContentStub).props('aggregationSteps')).toBeNull()
  })

  it('draws a single point as a marker', async () => {
    const { element } = await mountChart({
      data: { m1: { loss: [{ step: 5, value: 2 }] } },
      fullRange: { first: 5, last: 5 },
    })

    expect(lineOf('m1', element).mode).toBe('lines+markers')
    expect(lineOf('m1', element).marker).toMatchObject({ size: [ISOLATED_MARKER_SIZE] })
    expect(xRange(element)).toEqual([4, 6])
  })

  it('draws nothing but does not fail when every value is NULL', async () => {
    const { element } = await mountChart({
      data: { m1: { loss: points(0, 9, () => null) } },
      fullRange: { first: 0, last: 9 },
    })

    expect(lineOf('m1', element).y.every((value) => value === null)).toBe(true)
    expect((mock.lastCall(element).layout.yaxis as Record<string, unknown>).range).toBeUndefined()
  })

  it('places sparse negative steps far from zero at their bucket midpoints', async () => {
    const { element } = await mountChart({
      data: { m1: { loss: points(-1_000_000, -999_000, () => 1, 7) } },
      fullRange: { first: -1_000_000, last: -999_006 },
    })

    const line = lineOf('m1', element)
    expect(line.x.every((x) => x >= -1_000_000 && x <= -999_006)).toBe(true)
    expect(xRange(element)).toEqual([-1_000_000, -999_006])
  })

  it('re-renders with Plotly.react when the theme changes', async () => {
    const theme = ref('light')
    const { element } = await mountChart({
      data: LONG,
      fullRange: { first: 0, last: 9999 },
      theme,
    })
    const before = mock.calls.length

    theme.value = 'dark'
    await settle()

    expect(mock.calls.length).toBeGreaterThan(before)
    expect(mock.lastCall(element).traces).toHaveLength(2)
    // The band is denser on a dark background and follows the theme of a drawn chart.
    expect(traces(element)[0]?.fillcolor).toBe('rgba(17, 34, 51, 0.35)')
    theme.value = 'light'
    await settle()
    expect(traces(element)[0]?.fillcolor).toBe('rgba(17, 34, 51, 0.2)')
    expect(mock.plotly.newPlot).not.toHaveBeenCalled()
  })
})

describe('DynamicMetricsItem zoom', () => {
  it('requests the zoomed range with the width-derived budget and keeps the zoom across updates', async () => {
    setWidth(800)
    const { element, requests, store, source } = await mountChart({
      data: LONG,
      fullRange: { first: 0, last: 9999 },
    })
    expect(requests.at(-1)).toEqual({
      modelIds: ['m1'],
      keys: ['loss'],
      startStep: 0,
      endStep: 9999,
      bucketBudget: 800,
    })

    mock.fire(element, 'plotly_relayout', { 'xaxis.range[0]': 100.4, 'xaxis.range[1]': 199.6 })
    await settle()

    expect(requests.at(-1)).toMatchObject({ startStep: 100, endStep: 200, bucketBudget: 800 })
    expect(xRange(element)).toEqual([100.4, 199.6])
    expect(mock.lastCall(element).layout.uirevision).toBe('loss')
    expect(lineOf('m1', element).x[0]).toBe(100)

    source.data.m1 = { loss: points(0, 10_999, (step) => step % 10) }
    await store.refreshCatalogs(['m1'])
    await settle()

    expect(xRange(element)).toEqual([100.4, 199.6])
  })

  it('shows the coarser data on screen while the finer level loads, then the finer data', async () => {
    const { element, source, wrapper } = await mountChart({
      data: LONG,
      fullRange: { first: 0, last: 9999 },
    })
    const coarse = lineOf('m1', element)
    source.hold()

    mock.fire(element, 'plotly_relayout', { 'xaxis.range': [1000, 1999] })
    await settle()

    const provisional = lineOf('m1', element)
    expect(provisional.x.length).toBeGreaterThan(0)
    // The level 4 buckets that overlap steps 1000-1999, already on screen.
    expect(provisional.x).toEqual(coarse.x.filter((x) => x >= 895.5 && x <= 1919.5))
    expect(provisional.x).toHaveLength(5)
    expect(wrapper.findComponent(ContentStub).props('loading')).toBe(true)

    source.releaseAll()
    await settle()

    const fine = lineOf('m1', element)
    // Level 2 (16 steps per bucket) is the finest that fits 1,000 steps in 100 buckets.
    expect(fine.x[0]).toBe((992 + 1007) / 2)
    expect(wrapper.findComponent(ContentStub).props('loading')).toBe(false)
    expect(wrapper.findComponent(ContentStub).props('aggregationSteps')).toBe(16)
  })

  it('applies only the latest zoom when the level changes while a request is in flight', async () => {
    const { element, source } = await mountChart({
      data: LONG,
      fullRange: { first: 0, last: 9999 },
    })
    source.hold()

    mock.fire(element, 'plotly_relayout', { 'xaxis.range': [1000, 1999] })
    await settle()
    mock.fire(element, 'plotly_relayout', { 'xaxis.range': [1000, 1049] })
    await settle()
    source.releaseAll()
    await settle()

    const line = lineOf('m1', element)
    expect(line.x[0]).toBe(1000)
    expect(line.x.length).toBe(50)
    expect(source.abortedCalls).toBe(1)
  })

  it('resets to the full range on double-click', async () => {
    const { element, requests } = await mountChart({
      data: LONG,
      fullRange: { first: 0, last: 9999 },
    })
    mock.fire(element, 'plotly_relayout', { 'xaxis.range': [1000, 1999] })
    await settle()

    mock.fire(element, 'plotly_doubleclick')
    await settle()

    expect(requests.at(-1)).toMatchObject({ startStep: 0, endStep: 9999 })
    expect(xRange(element)).toEqual([0, 9999])
    expect(mock.lastCall(element).config.doubleClick).toBe(false)
  })

  it('autoranges y to the visible buckets, band included', async () => {
    const { element } = await mountChart({
      data: { m1: { loss: points(0, 199, (step) => (step < 100 ? step : 1000)) } },
      fullRange: { first: 0, last: 199 },
    })
    mock.fire(element, 'plotly_relayout', { 'xaxis.range': [0, 49] })
    await settle()

    const yaxis = mock.lastCall(element).layout.yaxis as Record<string, unknown>
    expect(yaxis.fixedrange).toBe(true)
    expect(yaxis.range).toEqual([0 - 49 * 0.05, 49 + 49 * 0.05])
  })

  it('asks for a new budget when the chart is resized', async () => {
    setWidth(400)
    const { requests } = await mountChart({ data: LONG, fullRange: { first: 0, last: 9999 } })
    expect(requests.at(-1)?.bucketBudget).toBe(400)

    setWidth(1200)
    resizeCallbacks.forEach((callback) => callback([], {} as ResizeObserver))
    await new Promise((resolve) => setTimeout(resolve, 150))
    await settle()

    expect(requests.at(-1)?.bucketBudget).toBe(1200)
  })
})

describe('DynamicMetricsItem comparison', () => {
  it('requests every experiment at one level and keeps the short one visible', async () => {
    const { element, source } = await mountChart({
      data: {
        m1: { loss: points(0, 99_999, () => 1) },
        m2: { loss: points(0, 299, () => 2) },
      },
      fullRange: { first: 0, last: 99_999 },
    })

    const levels = new Set(source.bucketCalls.map((call) => call.level))
    expect(levels.size).toBe(1)
    expect(source.bucketCalls.map((call) => call.modelIds)).toEqual([['m1'], ['m2']])
    const short = lineOf('m2', element)
    expect(short.y.length).toBeGreaterThan(0)
    expect(short.y.every((value) => value === 2)).toBe(true)
    expect(Math.max(...short.x)).toBeLessThanOrEqual(299)
    expect((lineOf('m2', element).line as Record<string, unknown>).color).toBe('#445566')
  })

  it('draws no trace for an experiment without the metric', async () => {
    const { element } = await mountChart({
      data: { m1: { loss: points(0, 9) }, m2: { acc: points(0, 9) } },
      fullRange: { first: 0, last: 9 },
    })

    expect(traces(element).map((trace) => trace.uid)).toEqual(['m1-line'])
  })

  it('draws the healthy experiments next to one in error', async () => {
    const source = new FakeBucketSource({ m1: { loss: points(0, 9) }, m2: { loss: points(0, 9) } })
    source.catalogErrors.add('m2')
    const store = new MetricBucketStore(source, { debounceMs: 0 })
    const wrapper = mount(DynamicMetricsItem, {
      props: {
        store,
        metricName: 'loss',
        modelIds: ['m1', 'm2'],
        fullRange: { first: 0, last: 9 },
        modelsInfo: MODELS,
      },
      global: {
        provide: { [ThemeKey]: ref('light') },
        stubs: { DynamicMetricsItemContent: ContentStub, ProgressSpinner: true },
      },
    })
    mounted.push(wrapper)
    await settle()

    expect(traces().map((trace) => trace.uid)).toEqual(['m1-line'])
    expect(wrapper.text()).not.toContain('Data could not be loaded.')
  })

  it('keeps the series drawn and shows the error in the card when a re-fetch fails', async () => {
    const { wrapper, source, store } = await mountChart({
      data: { m1: { loss: points(0, 9) } },
      fullRange: { first: 0, last: 99 },
    })
    const before = lineOf('m1').x
    expect(before.length).toBeGreaterThan(0)
    expect(wrapper.findComponent(ContentStub).props('error')).toBeNull()

    source.data.m1 = { loss: points(0, 19) }
    source.bucketErrors.add('m1')
    await store.refreshCatalogs(['m1'])
    await settle()

    expect(lineOf('m1').x).toEqual(before)
    expect(wrapper.findComponent(ContentStub).props('error')).toBe(
      'Model A: The experiment could not be read.',
    )
    expect(wrapper.findComponent(ContentStub).attributes('data-state')).toBe('error')
    expect(wrapper.text()).not.toContain('Data could not be loaded.')
  })

  it('still draws whole series when the cache bound is too small to hold them', async () => {
    const { element, store } = await mountChart({
      data: LONG,
      fullRange: { first: 0, last: 9999 },
      cache: new BucketCache({ maxBuckets: 2 }),
    })

    expect(lineOf('m1', element).x).toHaveLength(40)
    expect(store.cache).toBeInstanceOf(BucketCache)
  })
})

describe('DynamicMetricsItem lifecycle', () => {
  it('aborts its read and draws nothing more when unmounted during a load', async () => {
    const source = new FakeBucketSource(LONG)
    source.hold()
    const store = new MetricBucketStore(source, { debounceMs: 0 })
    const wrapper = mount(DynamicMetricsItem, {
      props: {
        store,
        metricName: 'loss',
        modelIds: ['m1'],
        fullRange: { first: 0, last: 9999 },
        modelsInfo: MODELS,
      },
      global: {
        provide: { [ThemeKey]: ref('light') },
        stubs: { DynamicMetricsItemContent: ContentStub, ProgressSpinner: true },
      },
    })
    await settle()
    expect(source.bucketCalls).toHaveLength(1)

    wrapper.unmount()
    const rendersAfterUnmount = mock.calls.length
    source.releaseAll()
    await settle()

    expect(source.abortedCalls).toBe(1)
    expect(mock.calls.length).toBe(rendersAfterUnmount)
  })

  it('fills the fullscreen chart opened during a load from the same read', async () => {
    setWidth(800)
    const { wrapper, source } = await mountChart({
      data: LONG,
      fullRange: { first: 0, last: 9999 },
    })
    const inline = wrapper.get('[data-testid="metric-plot"]').element as HTMLElement
    source.hold()
    mock.fire(inline, 'plotly_relayout', { 'xaxis.range': [1000, 1999] })
    await settle()

    const content = wrapper.findComponent(ContentStub)
    ;(content.vm as unknown as { scaled: boolean }).scaled = true
    await settle()
    const plots = wrapper.findAll('[data-testid="metric-plot"]')
    expect(plots).toHaveLength(2)
    const scaled = plots[1]?.element as HTMLElement
    expect(lineOf('m1', scaled).x.length).toBeGreaterThan(0)

    source.releaseAll()
    await settle()

    expect(lineOf('m1', scaled).x.length).toBeGreaterThan(0)
    expect(lineOf('m1', inline).x[0]).toBe(1000 + 1.5)
  })
})

describe('DynamicMetricsItem fullscreen status', () => {
  async function openFullscreen() {
    setWidth(800)
    const chart = await mountChart({ data: LONG, fullRange: { first: 0, last: 9999 } })
    const content = chart.wrapper.findComponent(ContentStub)
    ;(content.vm as unknown as { scaled: boolean }).scaled = true
    await settle()
    const [inline, scaled] = chart.wrapper
      .findAll('[data-testid="metric-plot"]')
      .map((plot) => plot.element as HTMLElement)
    const scaledStatus = () => chart.wrapper.get('[data-testid="scaled-status"]')
    return { ...chart, content, inline: inline!, scaled: scaled!, scaledStatus }
  }

  it('shows a failed and a loading zoom of the fullscreen chart in the fullscreen view only', async () => {
    const { source, content, scaled, scaledStatus } = await openFullscreen()
    expect(scaledStatus().find('[data-testid="chart-error"]').exists()).toBe(false)

    source.hold()
    mock.fire(scaled, 'plotly_relayout', { 'xaxis.range': [1000, 1999] })
    await settle()
    expect(scaledStatus().findComponent({ name: 'ProgressSpinner' }).exists()).toBe(true)
    expect(content.props('loading')).toBe(false)

    source.bucketErrors.add('m1')
    source.releaseAll()
    await settle()
    expect(lineOf('m1', scaled).x.length).toBeGreaterThan(0)
    expect(scaledStatus().find('[data-testid="chart-error"]').exists()).toBe(true)
    expect(scaledStatus().findComponent({ name: 'ProgressSpinner' }).exists()).toBe(false)
    expect(content.props('error')).toBeNull()
  })

  it('keeps a failed zoom of the card chart out of the fullscreen view', async () => {
    const { source, content, inline, scaledStatus } = await openFullscreen()
    source.bucketErrors.add('m1')
    mock.fire(inline, 'plotly_relayout', { 'xaxis.range': [1000, 1999] })
    await settle()

    expect(content.props('error')).toBe('Model A: The experiment could not be read.')
    expect(scaledStatus().find('[data-testid="chart-error"]').exists()).toBe(false)
  })

  it('explains the aggregation of the fullscreen chart', async () => {
    const { scaledStatus } = await openFullscreen()
    expect(scaledStatus().findComponent(CircleAlert).exists()).toBe(true)
  })
})

describe('DynamicMetricsItem draw state', () => {
  function cardState(wrapper: VueWrapper): string | undefined {
    return wrapper.findComponent(ContentStub).attributes('data-state')
  }

  function emittedStates(wrapper: VueWrapper): string[] {
    const events = wrapper.findComponent(MetricBucketPlot).emitted('status') ?? []
    return events.map(([status]) => (status as PlotStatus).state)
  }

  /** Resolves every pending draw but the newest, which a newer draw superseded. */
  async function settleSupersededDraws(): Promise<void> {
    while (mock.pendingDraws.length > 1) mock.settleDraw()
    await settle()
  }

  it('reports final only after Plotly has drawn the data', async () => {
    mock.holdDraws()
    const { wrapper } = await mountChart({ data: LONG, fullRange: { first: 0, last: 9999 } })
    expect(mock.pendingDraws.length).toBeGreaterThan(0)
    expect(cardState(wrapper)).toBe('loading')

    mock.releaseDraws()
    await settle()

    expect(cardState(wrapper)).toBe('final')
  })

  it('reports no stale final when a newer request supersedes a pending draw', async () => {
    mock.holdDraws()
    const { wrapper, source } = await mountChart({
      data: LONG,
      fullRange: { first: 0, last: 9999 },
    })
    source.hold()
    await wrapper.setProps({ fullRange: { first: 0, last: 4999 } })
    await settle()

    await settleSupersededDraws()
    expect(cardState(wrapper)).toBe('loading')

    mock.settleDraw()
    await settle()
    // The newest draw shows the first answer while the newer request loads.
    expect(cardState(wrapper)).toBe('provisional')
    expect(emittedStates(wrapper)).not.toContain('final')

    mock.releaseDraws()
    source.releaseAll()
    await settle()
    expect(cardState(wrapper)).toBe('final')
  })

  it('ends in the error state when Plotly fails to draw', async () => {
    mock.holdDraws()
    const { wrapper } = await mountChart({ data: LONG, fullRange: { first: 0, last: 9999 } })
    await settleSupersededDraws()

    mock.settleDraw(new Error('WebGL lost'))
    await settle()

    expect(cardState(wrapper)).toBe('error')
    expect(wrapper.findComponent(ContentStub).props('error')).toBe('Data could not be loaded.')
    expect(emittedStates(wrapper)).not.toContain('final')
  })

  it('ends in the error state when Plotly fails to load', async () => {
    const getPlotly = vi.mocked(plotlyService.getPlotly)
    getPlotly.mockRejectedValue(new Error('chunk failed'))
    try {
      const { wrapper } = await mountChart({
        data: { m1: { loss: points(0, 9) } },
        fullRange: { first: 0, last: 9 },
      })
      expect(cardState(wrapper)).toBe('error')
    } finally {
      getPlotly.mockImplementation(async () => plotlyMock.current as never)
    }
  })
})
