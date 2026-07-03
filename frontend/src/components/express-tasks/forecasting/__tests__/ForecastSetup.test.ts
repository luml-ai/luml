import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import ForecastSetup from '../ForecastSetup.vue'

const modelStub = (name: string) => ({
  name,
  props: ['modelValue'],
  emits: ['update:modelValue'],
  template: '<div />',
})

const defaults = {
  frequency: 'month' as const,
  previewEndDate: null,
  hasKnownFuture: false,
  lastHistoricalDate: new Date('2020-03-01'),
  dateNotParseable: false,
  previewDateInvalid: false,
}

function mountSetup(props: Partial<typeof defaults> = {}) {
  return mount(ForecastSetup, {
    props: { ...defaults, ...props },
    global: {
      components: { DSelect: modelStub('DSelect') },
      stubs: { DatePicker: modelStub('DatePicker') },
    },
  })
}

describe('ForecastSetup bar', () => {
  it('forwards frequency and preview date updates as v-model events', async () => {
    const wrapper = mountSetup()
    await wrapper.findComponent({ ref: 'frequencySelect' }).vm.$emit('update:modelValue', 'week')
    const previewDate = new Date('2020-06-01')
    await wrapper.findComponent({ ref: 'previewDate' }).vm.$emit('update:modelValue', previewDate)

    expect(wrapper.emitted('update:frequency')).toEqual([['week']])
    expect(wrapper.emitted('update:previewEndDate')).toEqual([[previewDate]])
  })

  it('hides the preview date picker and explains why with known-future columns', () => {
    const wrapper = mountSetup({ hasKnownFuture: true })
    expect(wrapper.findComponent({ ref: 'previewDate' }).exists()).toBe(false)
    expect(wrapper.find('[data-testid="preview-hint"]').exists()).toBe(true)
  })

  it('shows validation errors', () => {
    const wrapper = mountSetup({ dateNotParseable: true, previewDateInvalid: true })
    expect(wrapper.find('[data-testid="error-date-parseable"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="error-preview-date"]').exists()).toBe(true)
  })
})
