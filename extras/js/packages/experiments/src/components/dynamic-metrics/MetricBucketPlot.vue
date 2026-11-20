<template>
  <div class="plot-wrapper" :style="{ height }">
    <div ref="plotRef" class="plot" data-testid="metric-plot"></div>
    <div v-if="!shown.length && loading" class="plot-overlay">
      <ProgressSpinner style="width: 48px; height: 48px" />
    </div>
    <div v-else-if="!shown.length && failed" class="plot-overlay plot-message">
      Data could not be loaded.
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ModelInfo } from '@/interfaces/interfaces'
import type { PlotState, PlotStatus } from './dynamic-metrics.interface'
import type {
  ChartSeries,
  ChartState,
  ChartSubscription,
  MetricBucketStore,
} from '@/metric-buckets/MetricBucketStore'
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, unref, watch } from 'vue'
import { ProgressSpinner } from 'primevue'
import { useVariableValue } from '@/hooks/useVariableValue'
import { useInView } from '@/hooks/useInView'
import { useTheme } from '@/lib/theme/ThemeProvider'
import { plotlyLineChartLayout } from '@/lib/plotly/layouts'
import { cutStringOnMiddle } from '@/helpers/helpers'
import { plotlyService } from '@/services/PlotlyService'
import type { ExperimentReadErrorCode } from '@/metric-buckets/types'
import { readErrorText } from '@/components/experiment-status/readErrorText'
import {
  axisStepRange,
  BAND_OPACITY,
  DARK_BAND_OPACITY,
  bucketBudgetForWidth,
  buildBucketTraces,
  maxShownLevel,
  paddedRange,
  requestStepRange,
  visibleValueRange,
  type SeriesStyle,
  type StepRange,
} from '@/lib/metric-charts/bucketTraces'

const DRAW_ERROR_TEXT = 'Data could not be loaded.'

type Props = {
  store: MetricBucketStore
  metricName: string
  modelIds: string[]
  fullRange: StepRange
  modelsInfo: Record<string, ModelInfo>
  height: string
  /** Subscribe only while the plot is near the viewport. */
  lazy?: boolean
}

type Emits = {
  status: [PlotStatus]
}

type RelayoutEvent = Record<string, unknown>

type PlotElement = HTMLDivElement & {
  on?: (event: string, handler: (data: RelayoutEvent) => void) => void
}

const props = withDefaults(defineProps<Props>(), { lazy: false })
const emit = defineEmits<Emits>()

const { getVariablesValues } = useVariableValue()
const theme = useTheme()

const plotRef = ref<PlotElement | null>(null)
const inView = useInView(plotRef, props.lazy)
const shown = shallowRef<ChartSeries[]>([])
const loading = ref(false)
const failed = ref(false)
const errorText = ref<string | null>(null)
/** The user's zoomed x range; null shows the metric's whole range. */
const zoomRange = ref<[number, number] | null>(null)
const budget = ref(bucketBudgetForWidth(0))

let subscription: ChartSubscription | null = null
let shownStore: MetricBucketStore | null = null
let handlersAttached = false
let plotted = false
/** A chart that never got an answer is loading, not final, even while it waits off screen. */
let answered = false
let unmounted = false
/** The series Plotly has finished drawing; states that claim data on screen wait for it. */
let drawnSeries: ChartSeries[] | null = null
let drawFailed = false
let drawGeneration = 0
let resizeObserver: ResizeObserver | null = null
let resizeTimeout: ReturnType<typeof setTimeout> | null = null

const axisRange = computed<[number, number]>(
  () => zoomRange.value ?? axisStepRange(props.fullRange),
)

const requestRange = computed<StepRange>(() =>
  zoomRange.value ? requestStepRange(zoomRange.value, props.fullRange) : props.fullRange,
)

function styleOf(modelId: string): SeriesStyle {
  const info = props.modelsInfo[modelId]
  const [color] = getVariablesValues([info?.color ?? 'var(--p-primary-color)'])
  const name = info?.name ?? modelId
  return { name: name.length > 24 ? cutStringOnMiddle(name, 24) : name, color: color ?? '' }
}

function chartErrorText(modelId: string, code: ExperimentReadErrorCode): string {
  const name = props.modelsInfo[modelId]?.name ?? 'An experiment'
  return `${name}: ${readErrorText(code)}`
}

function onState(state: ChartState) {
  answered ||= !state.loading
  shown.value = state.series
  loading.value = state.loading
  failed.value = state.errors.length > 0
  const [first] = state.errors
  errorText.value = first ? chartErrorText(first.modelId, first.error.code) : null
  emitStatus()
  render()
}

function shownError(): string | null {
  return errorText.value ?? (drawFailed ? DRAW_ERROR_TEXT : null)
}

function chartState(): PlotState {
  if (shownError()) return 'error'
  if (!shown.value.length && (loading.value || !answered)) return 'loading'
  if (drawnSeries !== shown.value) return drawnSeries?.length ? 'provisional' : 'loading'
  if (loading.value || shown.value.some((series) => !series.final)) return 'provisional'
  return 'final'
}

function emitStatus() {
  emit('status', {
    level: maxShownLevel(shown.value),
    loading: loading.value,
    error: shownError(),
    state: chartState(),
  })
}

function syncSubscription() {
  if (!inView.value) {
    closeSubscription()
    return
  }
  if (shownStore !== props.store) {
    closeSubscription()
    // Another provider's data must not stand in for this one's.
    shown.value = []
    shownStore = props.store
  }
  // A new subscription (after scrolling back) keeps what is drawn until better data arrives.
  subscription ??= props.store.subscribe(onState, { series: shown.value })
  subscription.request({
    modelIds: props.modelIds,
    keys: [props.metricName],
    startStep: requestRange.value.first,
    endStep: requestRange.value.last,
    bucketBudget: budget.value,
  })
}

function closeSubscription() {
  if (!subscription) return
  subscription.close()
  subscription = null
  if (loading.value) {
    loading.value = false
    emitStatus()
  }
}

function buildLayout() {
  const [bgColor, borderColor, textColor, gridColor] = getVariablesValues([
    'var(--p-card-background)',
    'var(--p-content-border-color)',
    'var(--p-text-muted-color)',
    'var(--p-datatable-row-background)',
  ])
  const base = plotlyLineChartLayout({
    title: props.metricName,
    bgColor: bgColor ?? '',
    borderColor: borderColor ?? '',
    textColor: textColor ?? '',
    gridColor: gridColor ?? '',
  })
  const [first, last] = axisRange.value
  const values = visibleValueRange(shown.value, { first, last })
  return {
    ...base,
    uirevision: props.metricName,
    dragmode: 'zoom',
    xaxis: { ...base.xaxis, range: [first, last], autorange: false },
    yaxis: values
      ? { ...base.yaxis, fixedrange: true, autorange: false, range: paddedRange(values) }
      : { ...base.yaxis, fixedrange: true },
  }
}

async function render() {
  const element = plotRef.value
  // A theme change reaches every chart on the page; one never drawn waits until it is near.
  if (!element || (!inView.value && !plotted)) return
  const generation = ++drawGeneration
  const isCurrent = () => !unmounted && plotRef.value === element && generation === drawGeneration
  try {
    const Plotly = await plotlyService.getPlotly()
    if (!isCurrent()) return
    const series = shown.value
    const bandAlpha = unref(theme) === 'dark' ? DARK_BAND_OPACITY : BAND_OPACITY
    const traces = buildBucketTraces(series, styleOf, bandAlpha)
    await Plotly.react(element, traces, buildLayout(), {
      displayModeBar: false,
      responsive: true,
      doubleClick: false,
    })
    plotted = true
    attachHandlers(element)
    if (!isCurrent()) return
    drawnSeries = series
    drawFailed = false
  } catch {
    if (!isCurrent()) return
    drawFailed = true
  }
  emitStatus()
}

function attachHandlers(element: PlotElement) {
  if (handlersAttached || !element.on) return
  handlersAttached = true
  element.on('plotly_relayout', onRelayout)
  element.on('plotly_doubleclick', resetZoom)
}

function onRelayout(event: RelayoutEvent) {
  if (event['xaxis.autorange'] === true) {
    resetZoom()
    return
  }
  const pair = event['xaxis.range']
  const start = Array.isArray(pair) ? pair[0] : event['xaxis.range[0]']
  const end = Array.isArray(pair) ? pair[1] : event['xaxis.range[1]']
  if (typeof start === 'number' && typeof end === 'number') zoomRange.value = [start, end]
}

function resetZoom() {
  if (zoomRange.value === null) render()
  else zoomRange.value = null
}

async function onResize() {
  const element = plotRef.value
  if (!element) return
  budget.value = bucketBudgetForWidth(element.clientWidth)
  const Plotly = await plotlyService.getPlotly()
  if (!unmounted && plotRef.value === element) Plotly.Plots.resize(element)
}

function observeResize(element: HTMLElement) {
  resizeObserver = new ResizeObserver(() => {
    if (resizeTimeout) clearTimeout(resizeTimeout)
    resizeTimeout = setTimeout(onResize, 100)
  })
  resizeObserver.observe(element)
}

watch(
  [inView, () => props.store, () => props.modelIds, () => props.metricName, requestRange, budget],
  syncSubscription,
)

watch(zoomRange, render)
watch(theme, render)

onMounted(() => {
  const element = plotRef.value
  if (!element) return
  budget.value = bucketBudgetForWidth(element.clientWidth)
  observeResize(element)
  syncSubscription()
  // A chart far below the fold creates no Plotly instance until it scrolls near.
  if (inView.value) render()
})

onBeforeUnmount(async () => {
  unmounted = true
  closeSubscription()
  resizeObserver?.disconnect()
  if (resizeTimeout) clearTimeout(resizeTimeout)
  const element = plotRef.value
  if (!element) return
  const Plotly = await plotlyService.getPlotly()
  Plotly.purge?.(element)
})
</script>

<style scoped>
.plot-wrapper {
  position: relative;
  width: 100%;
}

.plot {
  height: 100%;
  width: 100%;
}

.plot-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}

.plot-message {
  font-size: 14px;
  color: var(--p-text-muted-color);
}
</style>
