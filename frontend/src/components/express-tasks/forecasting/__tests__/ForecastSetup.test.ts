import { mount, type VueWrapper } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import { nextTick } from 'vue'
import ForecastSetup from '../ForecastSetup.vue'
import type { ForecastSetupState } from '@/lib/data-processing/forecasting-setup'

const modelStub = (name: string) => ({
  name,
  props: ['modelValue'],
  emits: ['update:modelValue'],
  template: '<div />',
})

const columns = ['date', 'sales', 'promo']
const rows = [
  { date: new Date('2020-01-01'), sales: 1000, promo: 0 },
  { date: new Date('2020-02-01'), sales: 1100, promo: 1 },
  { date: new Date('2020-03-01'), sales: 1200, promo: 0 },
]

function mountSetup(
  props: { columns: string[]; rows: Record<string, unknown>[] } = { columns, rows },
) {
  return mount(ForecastSetup, {
    props,
    global: {
      components: { DSelect: modelStub('DSelect') },
      stubs: {
        MultiSelect: modelStub('MultiSelect'),
        DatePicker: modelStub('DatePicker'),
        SelectButton: modelStub('SelectButton'),
      },
    },
  })
}

function lastState(wrapper: VueWrapper): ForecastSetupState {
  const events = wrapper.emitted('change') as ForecastSetupState[][]
  return events[events.length - 1][0]
}

async function setValue(wrapper: VueWrapper, ref: string, value: unknown) {
  await wrapper.findComponent({ ref }).vm.$emit('update:modelValue', value)
  await nextTick()
}

describe('ForecastSetup defaults', () => {
  it('defaults the date to the first parseable column and target to the first non-date column', () => {
    const wrapper = mountSetup()
    const state = lastState(wrapper)
    expect(state.config.date_col).toBe('date')
    expect(state.config.target_col).toBe('sales')
    expect(state.config.frequency).toBe('month')
    expect(state.isValid).toBe(true)
  })
})

describe('ForecastSetup validations', () => {
  it('blocks when the date and target are the same column', async () => {
    const wrapper = mountSetup()
    await setValue(wrapper, 'targetSelect', 'date')

    expect(wrapper.find('[data-testid="error-same-columns"]').exists()).toBe(true)
    expect(lastState(wrapper).isValid).toBe(false)
  })

  it('blocks when no column parses as dates', () => {
    const wrapper = mountSetup({
      columns: ['a', 'b'],
      rows: [
        { a: 1, b: 2 },
        { a: 3, b: 4 },
      ],
    })

    expect(wrapper.find('[data-testid="error-date-parseable"]').exists()).toBe(true)
    expect(lastState(wrapper).isValid).toBe(false)
  })

  it('blocks when the preview end date is not after the last historical date', async () => {
    const wrapper = mountSetup()
    await setValue(wrapper, 'previewDate', new Date('2020-02-15'))

    expect(wrapper.find('[data-testid="error-preview-date"]').exists()).toBe(true)
    expect(lastState(wrapper).isValid).toBe(false)
  })

  it('accepts a preview end date after the last history and computes the horizon', async () => {
    const wrapper = mountSetup()
    await setValue(wrapper, 'previewDate', new Date('2020-06-01'))

    const state = lastState(wrapper)
    expect(state.isValid).toBe(true)
    expect(state.config.preview_horizon).toBe(3)
  })
})

describe('ForecastSetup known-future handling', () => {
  it('hides the preview and sends no horizon when a column is marked known-future', async () => {
    const wrapper = mountSetup()
    await setValue(wrapper, 'auxSelect', ['promo'])
    await setValue(wrapper, 'knownFutureSelect', ['promo'])

    expect(wrapper.findComponent({ ref: 'previewDate' }).exists()).toBe(false)
    expect(wrapper.find('[data-testid="preview-hint"]').exists()).toBe(true)

    const state = lastState(wrapper)
    expect(state.config.aux_cols).toEqual(['promo'])
    expect(state.config.known_future_cols).toEqual(['promo'])
    expect(state.config.preview_horizon).toBeNull()
  })

  it('prunes known-future columns that are no longer auxiliaries', async () => {
    const wrapper = mountSetup()
    await setValue(wrapper, 'auxSelect', ['promo'])
    await setValue(wrapper, 'knownFutureSelect', ['promo'])
    await setValue(wrapper, 'auxSelect', [])

    expect(lastState(wrapper).config.known_future_cols).toEqual([])
  })
})
