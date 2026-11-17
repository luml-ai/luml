import { test, expect, type Page } from '@playwright/test'
import { build } from 'esbuild'
import { build as viteBuild, type Rollup } from 'vite'
import vue from '@vitejs/plugin-vue'
import { createServer, type Server } from 'node:http'
import type { AddressInfo } from 'node:net'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import type { MetricBucket } from '../../../extras/js/packages/experiments/src/metric-buckets/types'

// Draws the real metric chart traces with the real plotly.js-basic-dist-min in Chromium and
// checks the SVG Plotly renders: unit tests mock Plotly, and Plotly ignores some trace fields
// silently.

const here = dirname(fileURLToPath(import.meta.url))
const require = createRequire(import.meta.url)
const EXPERIMENTS_SRC = resolve(here, '../../../extras/js/packages/experiments/src')
const PLOTLY = require.resolve('plotly.js-basic-dist-min')
const THEMES = {
  light: { alpha: 0.2, background: '#ffffff', colors: ['#2673fd', '#d62728', '#2ca02c'] },
  dark: { alpha: 0.35, background: '#18181b', colors: ['#2462d0', '#b12526', '#298629'] },
}
type ThemeName = keyof typeof THEMES

interface Series {
  modelId: string
  key: string
  level: number
  final: boolean
  buckets: MetricBucket[]
}

let harness = ''

test.beforeAll(async () => {
  const result = await build({
    stdin: {
      contents: [
        "export { buildBucketTraces, visibleValueRange, paddedRange, axisStepRange, BAND_OPACITY, DARK_BAND_OPACITY } from '@/lib/metric-charts/bucketTraces'",
        "export { plotlyLineChartLayout } from '@/lib/plotly/layouts'",
      ].join('\n'),
      resolveDir: EXPERIMENTS_SRC,
      loader: 'ts',
    },
    bundle: true,
    format: 'iife',
    globalName: 'metricChart',
    platform: 'browser',
    write: false,
    alias: { '@': EXPERIMENTS_SRC },
    logLevel: 'silent',
  })
  harness = result.outputFiles[0]!.text
})

function bucket(index: number, values: number[], width = 16): MetricBucket {
  const drawn = values.filter((value) => Number.isFinite(value) && Math.abs(value) <= 1e290)
  const numeric = values.filter((value) => !Number.isNaN(value))
  return {
    bucket: index,
    first_step: index * width,
    last_step: index * width + width - 1,
    count: values.length,
    finite_count: drawn.length,
    min: numeric.length ? Math.min(...numeric) : null,
    max: numeric.length ? Math.max(...numeric) : null,
    sum: drawn.length ? drawn.reduce((total, value) => total + value, 0) : null,
  }
}

/** A bucket whose values lie evenly in `[low, high]`. */
function spread(index: number, low: number, high: number): MetricBucket {
  return bucket(index, [low, (low + high) / 2, high])
}

function series(modelId: string, buckets: MetricBucket[], level = 2): Series {
  return { modelId, key: 'loss', level, final: true, buckets }
}

async function draw(
  page: Page,
  shown: Series[],
  full: { first: number; last: number },
  themeName: ThemeName = 'light',
) {
  const theme = THEMES[themeName]
  await page.setViewportSize({ width: 700, height: 300 })
  await page.setContent('<div id="plot" style="width:640px;height:200px"></div>')
  await page.addScriptTag({ path: PLOTLY })
  await page.addScriptTag({ content: harness })
  await page.evaluate(
    async ({ shown, full, colors, background, dark }) => {
      const chart = (
        window as unknown as {
          metricChart: Record<string, CallableFunction> & Record<`${string}OPACITY`, number>
        }
      ).metricChart
      // As MetricBucketPlot picks the band alpha by theme.
      const alpha = dark ? chart.DARK_BAND_OPACITY : chart.BAND_OPACITY
      const traces = chart.buildBucketTraces(
        shown,
        (modelId: string) => ({
          name: modelId,
          color: colors[shown.findIndex((item) => item.modelId === modelId)],
        }),
        alpha,
      )
      const base = chart.plotlyLineChartLayout({
        title: 'loss',
        bgColor: background,
        borderColor: '#e2e8f0',
        textColor: '#64748b',
        gridColor: '#f8fafc',
      })
      const [first, last] = chart.axisStepRange(full)
      const values = chart.visibleValueRange(shown, { first, last })
      const layout = {
        ...base,
        xaxis: { ...base.xaxis, range: [first, last], autorange: false },
        yaxis: { ...base.yaxis, autorange: false, range: chart.paddedRange(values) },
      }
      const plotly = (window as unknown as { Plotly: { newPlot: CallableFunction } }).Plotly
      await plotly.newPlot(document.getElementById('plot'), traces, layout, {
        displayModeBar: false,
      })
    },
    {
      shown,
      full,
      colors: theme.colors,
      background: theme.background,
      dark: themeName === 'dark',
    },
  )
}

interface FillInfo {
  uid: string
  opacity: number
  /** The x extent, in steps, of each closed polygon of the fill. */
  polygons: [number, number][]
}

async function fills(page: Page): Promise<FillInfo[]> {
  return page.evaluate(() => {
    const element = document.getElementById('plot') as HTMLElement & {
      _fullLayout: { xaxis: { p2l: (px: number) => number } }
    }
    const xaxis = element._fullLayout.xaxis
    return [...element.querySelectorAll<SVGPathElement>('g.trace path.js-fill')].map((path) => {
      const group = path.closest('g.trace') as SVGGElement & {
        __data__?: [{ trace: { uid: string } }]
      }
      const polygons = (path.getAttribute('d') ?? '')
        .split('M')
        .filter(Boolean)
        .map((part): [number, number] => {
          const xs = [...part.matchAll(/(-?[\d.]+),(-?[\d.]+)/g)].map((match) =>
            xaxis.p2l(Number(match[1])),
          )
          return [Math.min(...xs), Math.max(...xs)]
        })
      return {
        uid: group.__data__?.[0]?.trace.uid ?? '',
        opacity: Number(getComputedStyle(path).fillOpacity),
        polygons,
      }
    })
  })
}

/** The edges of the band fill polygons, as pairs of [step, value] vertices. */
async function bandEdges(page: Page): Promise<[number, number][][]> {
  return page.evaluate(() => {
    const element = document.getElementById('plot') as HTMLElement & {
      _fullLayout: Record<'xaxis' | 'yaxis', { p2l: (px: number) => number }>
    }
    const { xaxis, yaxis } = element._fullLayout
    const paths = [...element.querySelectorAll<SVGPathElement>('g.trace path.js-fill')]
    return paths.flatMap((path) =>
      (path.getAttribute('d') ?? '')
        .split('M')
        .filter(Boolean)
        .flatMap((polygon) => {
          const vertices = [...polygon.matchAll(/(-?[\d.]+),(-?[\d.]+)/g)].map(
            (match): [number, number] => [xaxis.p2l(Number(match[1])), yaxis.p2l(Number(match[2]))],
          )
          return vertices.map((vertex, index) => [vertex, vertices[(index + 1) % vertices.length]!])
        }),
    )
  })
}

/** The pixel colour at a data point, read from a screenshot of the plot. */
async function pixelAt(page: Page, step: number, value: number): Promise<number[]> {
  const shot = (await page.screenshot()).toString('base64')
  return page.evaluate(
    async ({ shot, step, value }) => {
      const element = document.getElementById('plot') as HTMLElement & {
        _fullLayout: Record<'xaxis' | 'yaxis', { l2p: (v: number) => number; _offset: number }>
      }
      const { xaxis, yaxis } = element._fullLayout
      const box = element.getBoundingClientRect()
      const x = Math.round(box.left + xaxis._offset + xaxis.l2p(step))
      const y = Math.round(box.top + yaxis._offset + yaxis.l2p(value))
      const image = await createImageBitmap(
        await (await fetch(`data:image/png;base64,${shot}`)).blob(),
      )
      const canvas = new OffscreenCanvas(image.width, image.height)
      const context = canvas.getContext('2d')!
      context.drawImage(image, 0, 0)
      return [...context.getImageData(x, y, 1, 1).data.slice(0, 3)]
    },
    { shot, step, value },
  )
}

test.describe('metric chart rendering', () => {
  test('draws the band lighter than its line, and the line above every band', async ({ page }) => {
    const buckets = Array.from({ length: 12 }, (_, index) =>
      spread(index, Math.sin(index / 2) - 1, Math.sin(index / 2) + 1),
    )
    await draw(page, [series('m1', buckets)], { first: 0, last: 191 })

    const [band, ...others] = await fills(page)
    expect(others).toEqual([])
    expect(band!.uid).toBe('m1-band')
    expect(band!.opacity).toBeCloseTo(THEMES.light.alpha, 5)

    const order = await page.evaluate(() => {
      const fill = document.querySelector('path.js-fill')!
      const line = [...document.querySelectorAll<SVGPathElement>('path.js-line')].find(
        (path) => Number(getComputedStyle(path).strokeWidth.replace('px', '')) > 0,
      )
      return line ? fill.compareDocumentPosition(line) & Node.DOCUMENT_POSITION_FOLLOWING : 0
    })
    expect(order).toBeTruthy()
  })

  test('leaves the band out across buckets with no finite value', async ({ page }) => {
    const empty = (index: number) => bucket(index, [Number.NaN])
    const buckets = [
      ...[0, 1, 2, 3].map((index) => spread(index, 0, 2)),
      empty(4),
      empty(5),
      ...[6, 7, 8].map((index) => spread(index, 1, 3)),
      empty(9),
      spread(10, 0, 1),
      empty(11),
    ]
    await draw(page, [series('m1', buckets)], { first: 0, last: 191 })

    const [band] = await fills(page)
    const midpoint = (index: number) => index * 16 + 7.5
    for (const gap of [4, 5, 9, 11]) {
      for (const [low, high] of band!.polygons) {
        expect(low > midpoint(gap) || high < midpoint(gap), `fill crosses bucket ${gap}`).toBe(true)
      }
    }
    const markers = await page.locator('g.trace path.point').count()
    expect(markers).toBeGreaterThan(0)
  })

  for (const themeName of Object.keys(THEMES) as ThemeName[]) {
    test(`blends the bands of three experiments of different lengths (${themeName})`, async ({
      page,
    }) => {
      const { alpha, background } = THEMES[themeName]
      const backgroundRgb = [1, 3, 5].map((at) => parseInt(background.slice(at, at + 2), 16))
      const constant = (count: number, low: number, high: number) =>
        Array.from({ length: count }, (_, index) => spread(index, low, high))
      await draw(
        page,
        [
          series('aaaaaaaa-0000-4000-8000-000000000001', constant(12, 0, 2)),
          series('aaaaaaaa-0000-4000-8000-000000000002', constant(8, 1, 3)),
          series('aaaaaaaa-0000-4000-8000-000000000003', constant(5, 4, 6)),
        ],
        { first: 0, last: 191 },
        themeName,
      )

      const drawn = await fills(page)
      expect(drawn).toHaveLength(3)
      for (const fill of drawn) expect(fill.opacity).toBeCloseTo(alpha, 5)

      const uidsAreSelectors = await page.evaluate(() => {
        const element = document.getElementById('plot') as HTMLElement & {
          _fullData: { uid: string }[]
        }
        return element._fullData.every(({ uid }) => {
          try {
            document.querySelector(`.cb${uid}`)
            return true
          } catch {
            return false
          }
        })
      })
      expect(uidsAreSelectors).toBe(true)

      const firstOnly = await pixelAt(page, 40, 0.5)
      const overlap = await pixelAt(page, 40, 1.5)
      const secondOnly = await pixelAt(page, 40, 2.5)
      expect(overlap).not.toEqual(firstOnly)
      expect(overlap).not.toEqual(secondOnly)
      expect(firstOnly).not.toEqual(backgroundRgb)
      expect(secondOnly).not.toEqual(backgroundRgb)
    })
  }

  test('steps the band: a spike is no wider than the steps of its own bucket', async ({ page }) => {
    const buckets = Array.from({ length: 30 }, (_, index) => spread(index, 0, 1))
    buckets[15] = spread(15, 0, 10)
    await draw(page, [series('m1', buckets)], { first: 0, last: 479 })

    // Every edge above the other buckets' maximum belongs to the spike bucket (steps 240-255),
    // give or take the one-step jump to a neighbour.
    const raised = (await bandEdges(page)).filter((edge) => edge.some(([, value]) => value > 1.5))
    expect(raised.length).toBeGreaterThan(0)
    for (const [step] of raised.flat()) {
      expect(step).toBeGreaterThan(239 - 0.5)
      expect(step).toBeLessThan(256 + 0.5)
    }
  })

  test('fits the y-range to drawn values when the data holds 1e300 and infinities', async ({
    page,
  }) => {
    const buckets = Array.from({ length: 12 }, (_, index) => spread(index, -1, 1))
    buckets[3] = bucket(3, [-1, 0, 1, 1e300])
    buckets[6] = bucket(6, [-1, 0, Infinity, -Infinity])
    buckets[9] = bucket(9, [1e300, -1e300])
    await draw(page, [series('m1', buckets)], { first: 0, last: 191 })

    const range = await page.evaluate(
      () =>
        (
          document.getElementById('plot') as HTMLElement & {
            _fullLayout: { yaxis: { range: [number, number] } }
          }
        )._fullLayout.yaxis.range,
    )
    expect(range[0]).toBeGreaterThan(-2)
    expect(range[1]).toBeLessThan(2)

    const [band] = await fills(page)
    const gap = 9 * 16 + 7.5
    for (const [low, high] of band!.polygons) expect(low > gap || high < gap).toBe(true)
  })
})

const HARNESS_ID = 'virtual:metric-chart-harness'

// The real chart component in a page that loads Plotly as its own chunk, as the app does. Each
// time a card turns `final`, the observer notes what Plotly had drawn at that very moment.
const CHART_HARNESS = `
import { createApp, h, ref } from 'vue'
import PrimeVue from 'primevue/config'
import Tooltip from 'primevue/tooltip'
import DynamicMetricsItem from '@/components/dynamic-metrics/DynamicMetricsItem.vue'
import { ThemeKey } from '@/lib/theme/ThemeProvider'

window.finalSeen = []
new MutationObserver((records) => {
  for (const record of records) {
    const card = record.target
    if (card.getAttribute('data-state') !== 'final') continue
    window.finalSeen.push({
      svg: card.querySelectorAll('.main-svg').length,
      traces: card.querySelectorAll('.scatterlayer .trace path.js-line').length,
    })
  }
}).observe(document.body, { subtree: true, attributes: true, attributeFilter: ['data-state'] })

const buckets = Array.from({ length: 50 }, (_, step) => ({
  bucket: step,
  first_step: step,
  last_step: step,
  count: 1,
  finite_count: 1,
  min: step % 7,
  max: step % 7,
  sum: step % 7,
}))
const series = [{ modelId: 'm1', key: 'loss', level: 0, final: true, buckets }]
const store = {
  subscribe(listener) {
    return {
      state: null,
      request(request) {
        setTimeout(() =>
          listener({ request, plan: null, loading: false, series, errors: [], cacheOverflow: false }),
        )
      },
      close() {},
    }
  },
}

createApp({
  render: () =>
    h(DynamicMetricsItem, {
      store,
      metricName: 'loss',
      modelIds: ['m1'],
      fullRange: { first: 0, last: 49 },
      modelsInfo: { m1: { name: 'Model A', color: '#2673fd' } },
    }),
})
  .use(PrimeVue, { unstyled: true })
  .directive('tooltip', Tooltip)
  .provide(ThemeKey, ref('light'))
  .mount('#app')
`

test.describe('metric chart state', () => {
  let server: Server
  let origin = ''

  test.beforeAll(async () => {
    test.setTimeout(180_000)
    const output = (await viteBuild({
      configFile: false,
      root: resolve(EXPERIMENTS_SRC, '..'),
      base: './',
      logLevel: 'silent',
      plugins: [
        vue(),
        {
          name: 'metric-chart-harness',
          resolveId: (id) => (id === HARNESS_ID ? `\0${HARNESS_ID}` : null),
          load: (id) => (id === `\0${HARNESS_ID}` ? CHART_HARNESS : null),
        },
      ],
      resolve: { alias: { '@': EXPERIMENTS_SRC } },
      css: { postcss: {} },
      build: {
        write: false,
        minify: false,
        rollupOptions: { input: HARNESS_ID },
      },
    })) as Rollup.RollupOutput
    const files = new Map<string, string | Uint8Array>(
      output.output.map((file) => [
        `/${file.fileName}`,
        file.type === 'chunk' ? file.code : file.source,
      ]),
    )
    const entry = output.output.find((file) => file.type === 'chunk' && file.isEntry)!
    files.set(
      '/',
      `<!doctype html><div id="app" style="width:640px"></div>` +
        `<script type="module" src="./${entry.fileName}"></script>`,
    )
    server = createServer((request, response) => {
      const path = new URL(request.url!, 'http://harness').pathname
      const body = files.get(path)
      if (body === undefined) {
        response.writeHead(404).end()
        return
      }
      const type =
        path === '/' ? 'text/html' : path.endsWith('.js') ? 'text/javascript' : 'text/css'
      response.writeHead(200, { 'Content-Type': type }).end(body)
    })
    await new Promise<void>((done) => server.listen(0, '127.0.0.1', done))
    origin = `http://127.0.0.1:${(server.address() as AddressInfo).port}`
  })

  test.afterAll(async () => {
    await new Promise((done) => server?.close(done))
  })

  test('a chart turns final only once Plotly has drawn its trace', async ({ page }) => {
    await page.goto(origin)
    const card = page.locator('[data-testid="metric-chart"]')
    await expect(card).toHaveAttribute('data-state', 'final', { timeout: 30_000 })

    const seen = await page.evaluate(
      () => (window as unknown as { finalSeen: { svg: number; traces: number }[] }).finalSeen,
    )
    expect(seen.length).toBeGreaterThan(0)
    for (const moment of seen) {
      expect(moment.svg).toBeGreaterThan(0)
      expect(moment.traces).toBeGreaterThan(0)
    }
  })
})
