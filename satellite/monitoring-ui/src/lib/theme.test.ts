import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { applyTheme, initTheme, type Theme } from './theme'
import SeriesChart from '@/components/SeriesChart.vue'
import DistributionChart from '@/components/feature-drift/DistributionChart.vue'
import PredictionTrendChart from '@/components/output-drift/PredictionTrendChart.vue'
import ClassShareChart from '@/components/output-drift/ClassShareChart.vue'

const styles = document.createElement('style')
styles.textContent = ['luml-design-system.css', 'dashboard.css']
  .map((file) => readFileSync(resolve('src/assets', file), 'utf8'))
  .join('\n')
  .replace(/@import[^;]+;/g, '')

function appColors(theme: Theme): Record<string, string> {
  const css = readFileSync(resolve('../../frontend/src/assets/theme', `${theme}-theme.css`), 'utf8')
  return Object.fromEntries(
    [...css.matchAll(/--p-([\w-]+):\s*([^;]+);/g)].map(([, key, value]) => [key, value]),
  )
}

function color(token: string): string {
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(`--luml-${token}`)
    .trim()
  const reference = /^var\(--luml-([\w-]+)\)$/.exec(value)
  return reference ? color(reference[1]) : value
}

const ApexStub = {
  name: 'apexchart',
  props: ['options', 'series', 'height', 'type'],
  template: '<div />',
}

beforeEach(() => document.head.appendChild(styles))
afterEach(() => {
  styles.remove()
  applyTheme('light')
})

describe.each(['light', 'dark'] as const)('%s monitoring palette', (theme) => {
  it('matches the app surfaces, text, accents and status colors', () => {
    applyTheme(theme)
    const app = appColors(theme)
    const tokens = {
      bg: 'content-background',
      'bg-hover': 'content-hover-background',
      'bg-card': 'card-background',
      border: 'content-border-color',
      'border-strong': 'form-field-border-color',
      fg: 'text-color',
      'fg-strong': 'text-hover-color',
      'fg-muted': 'text-muted-color',
      'fg-faint': 'list-option-icon-color',
      brand: 'primary-color',
      'brand-hover': 'primary-hover-color',
      'brand-active': 'primary-active-color',
      'brand-contrast': 'primary-contrast-color',
      'brand-tint': 'highlight-background',
      'brand-tint-strong': 'highlight-focus-background',
      success: 'button-success-background',
      info: 'button-info-background',
      warn: 'button-warn-background',
      danger: 'button-danger-background',
      'success-tint-bg': 'tag-success-background',
      'success-tint-fg': 'tag-success-color',
      'info-tint-bg': 'tag-info-background',
      'info-tint-fg': 'tag-info-color',
      'warn-tint-bg': 'tag-warn-background',
      'warn-tint-fg': 'tag-warn-color',
      'danger-tint-bg': 'tag-danger-background',
      'danger-tint-fg': 'tag-danger-color',
      'surface-0': 'card-background',
      'surface-50': theme === 'dark' ? 'content-hover-background' : 'content-background',
      'surface-100': theme === 'dark' ? 'list-option-focus-background' : 'surface-100',
      'surface-200': 'content-border-color',
    }
    for (const [monitoring, platform] of Object.entries(tokens)) {
      expect(color(monitoring), monitoring).toBe(app[platform])
    }
    for (let index = 1; index <= 14; index++) {
      expect(color(`chart-${index}`)).toBe(app[`charts-color-${index}`])
    }
    for (let index = 1; index <= 6; index++) {
      expect(color(`span-icon-${index}`)).toBe(app[`trace-span-icon-color-${index}`])
    }
  })
})

it('updates chart series, grid, labels, thresholds and legends when the iframe theme changes', async () => {
  applyTheme('light')
  initTheme()
  const series = {
    key: 'requests',
    label: 'Requests',
    points: [],
    baseline: [{ t: '2026-09-01T00:00:00Z', value: 1 }],
  }
  const wrappers = [
    mount(SeriesChart, {
      props: { series, threshold: 10 },
      global: { stubs: { apexchart: ApexStub } },
    }),
    mount(DistributionChart, {
      props: { distribution: { kind: 'numeric', bins: [] } },
      global: { stubs: { apexchart: ApexStub } },
    }),
    mount(PredictionTrendChart, {
      props: { trend: [] },
      global: { stubs: { apexchart: ApexStub } },
    }),
    mount(ClassShareChart, { props: { series: [] }, global: { stubs: { apexchart: ApexStub } } }),
  ]
  for (const theme of ['light', 'dark', 'light'] as const) {
    window.dispatchEvent(
      new MessageEvent('message', {
        source: window.parent,
        data: { type: 'monitoring:theme', theme },
      }),
    )
    await nextTick()
    const app = appColors(theme)
    expect(document.documentElement.dataset.theme).toBe(theme)
    for (const wrapper of wrappers) {
      const options = wrapper.findComponent(ApexStub).props('options')
      expect(options.grid.borderColor).toBe(app['content-border-color'])
      expect(options.chart.foreColor).toBe(app['text-muted-color'])
      expect(options.xaxis.labels.style.colors).toBe(app['text-muted-color'])
      expect(options.yaxis.labels.style.colors).toBe(app['text-muted-color'])
      expect(options.tooltip.theme).toBe(theme)
    }
    const [main, distribution, prediction, classes] = wrappers.map((wrapper) =>
      wrapper.findComponent(ApexStub).props('options'),
    )
    expect(main.colors).toEqual([app['charts-color-1'], app['text-muted-color']])
    expect(main.annotations.yaxis[0].borderColor).toBe(app['text-muted-color'])
    expect(main.annotations.yaxis[0].label.style.color).toBe(app['text-muted-color'])
    expect(distribution.colors).toEqual([app['text-muted-color'], app['charts-color-1']])
    expect(prediction.colors).toEqual([
      app['charts-color-1'],
      app['charts-color-1'],
      app['text-muted-color'],
    ])
    expect(classes.colors).toEqual(
      Array.from({ length: 14 }, (_, index) => app[`charts-color-${index + 1}`]),
    )
  }
  wrappers.forEach((wrapper) => wrapper.unmount())
})
