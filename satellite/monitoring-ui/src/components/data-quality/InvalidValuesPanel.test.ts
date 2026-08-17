import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import InvalidValuesPanel from './InvalidValuesPanel.vue'
import { Severity, type DataQualityFeatureRow, type Series } from '@/api/types'
import { makeDataQuality } from '@/test/fixtures'

function rowFor(feature: string): DataQualityFeatureRow {
  return makeDataQuality().features.find((row) => row.feature === feature)!
}

function mountPanel(row: DataQualityFeatureRow, extra: Record<string, unknown> = {}) {
  return mount(InvalidValuesPanel, {
    props: { row, ...extra },
    global: { stubs: { apexchart: true } },
  })
}

const TREND: Series = {
  key: 'unseen_category',
  label: 'Unseen categories',
  unit: 'ratio',
  points: [
    { t: '2026-08-18T13:00:00Z', value: 0 },
    { t: '2026-08-18T14:00:00Z', value: 0.1 },
  ],
}

describe('InvalidValuesPanel', () => {
  it('explains a numerical feature with the bounds it violated', () => {
    const wrapper = mountPanel(rowFor('age'))

    const checks = wrapper.findAll('[data-testid="dq-check"]').map((row) => row.text())
    // the rate the table shows, plus the counts behind it
    expect(checks[0]).toContain('0.1% · 1 of 1,070')
    expect(checks[2]).toContain('Out of range')
    expect(checks[2]).toContain('2.0% · 21 of 1,070')

    const range = wrapper.find('[data-testid="dq-out-of-range"]').text()
    expect(range).toContain('18 … 64') // reference bounds
    expect(range).toContain('3 … 122') // observed extremes
    expect(wrapper.find('[data-testid="dq-unseen-categories"]').exists()).toBe(false)
  })

  it('flags the rates that breached their spec threshold, like the table does', () => {
    const numerical = mountPanel(rowFor('age'))
    const numericalChecks = numerical.findAll('[data-testid="dq-check"]')
    // 0.1% missing is under the 1% warning line; 2.0% out of range is over it
    expect(numericalChecks[0].find('.warn, .critical').exists()).toBe(false)
    expect(numericalChecks[2].find('.warn').text()).toContain('2.0%')

    const categorical = mountPanel(rowFor('region'))
    const categoricalChecks = categorical.findAll('[data-testid="dq-check"]')
    expect(categoricalChecks[0].find('.critical').text()).toContain('20.0%') // missing > 5%
    expect(categoricalChecks[2].find('.critical').text()).toContain('10.0%') // unseen > 1%
  })

  it('names the unseen categories and how often each arrived', () => {
    const wrapper = mountPanel(rowFor('region'))

    const unseen = wrapper.find('[data-testid="dq-unseen-categories"]')
    expect(unseen.text()).toContain('antarctica')
    expect(unseen.text()).toContain('90')
    expect(unseen.text()).toContain('2 distinct values')
    expect(unseen.text()).toContain('4 categories')

    // the wrong-typed values are reported by type, with an example
    const types = wrapper.find('[data-testid="dq-type-errors"]').text()
    expect(types).toContain('int')
    expect(types).toContain('7')
    expect(wrapper.find('[data-testid="dq-out-of-range"]').exists()).toBe(false)
  })

  it('reports the categories it had to leave out of the list', () => {
    const row = rowFor('region')
    const wrapper = mountPanel({
      ...row,
      invalid: { ...row.invalid!, unseen_distinct: 12 },
    })

    expect(wrapper.find('[data-testid="dq-unseen-categories"]').text()).toContain(
      'and 10 more distinct values',
    )
  })

  it('still lists the checks when a window rejected nothing', () => {
    const wrapper = mountPanel({
      feature: 'sex',
      kind: 'categorical',
      missing_rate: 0,
      type_error_rate: 0,
      range_unseen_rate: 0,
      unseen_category_rate: 0,
      checked: 1070,
      status: Severity.OK,
      invalid: null,
    })

    expect(wrapper.find('[data-testid="dq-no-invalid"]').text()).toContain('matched the model')
    expect(wrapper.findAll('[data-testid="dq-check"]')).toHaveLength(3)
    expect(wrapper.find('[data-testid="dq-unseen-categories"]').exists()).toBe(false)
  })

  it('does not claim a clean window when the rates say otherwise', () => {
    // windows materialized before the breakdown was recorded carry rates but no evidence
    const wrapper = mountPanel({ ...rowFor('region'), invalid: null })

    expect(wrapper.find('[data-testid="dq-no-invalid"]').text()).toContain(
      'computed before the per-value breakdown',
    )
  })
})

describe('InvalidValuesPanel trends', () => {
  it('charts each check that has a history', () => {
    const wrapper = mountPanel(rowFor('region'), { trends: [TREND], trendsStatus: 'ready' })

    const trends = wrapper.find('[data-testid="dq-trends"]')
    expect(trends.text()).toContain('Unseen categories')
    expect(trends.findAll('apexchart-stub')).toHaveLength(1)
    expect(wrapper.find('[data-testid="dq-trends-empty"]').exists()).toBe(false)
  })

  it('explains why a single window has no chart yet', () => {
    const wrapper = mountPanel(rowFor('region'), { trends: [], trendsStatus: 'ready' })

    expect(wrapper.find('[data-testid="dq-trends-empty"]').text()).toContain('not a trend')
  })

  it('says it is still loading the history', () => {
    const wrapper = mountPanel(rowFor('region'), { trends: [], trendsStatus: 'loading' })

    expect(wrapper.find('[data-testid="dq-trends"]').text()).toContain('Loading history')
  })
})
