import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { CircleAlert } from 'lucide-vue-next'
import DynamicMetricsItemContent from '../DynamicMetricsItemContent.vue'

function mountContent(aggregated: boolean) {
  return mount(DynamicMetricsItemContent, {
    props: { title: 'loss', loading: false, aggregated },
    global: {
      directives: { tooltip: {} },
      stubs: {
        UiScalable: { template: '<div><slot /></div>' },
        Button: true,
        ProgressSpinner: true,
      },
    },
  })
}

describe('DynamicMetricsItemContent aggregated warning', () => {
  it('shows the "contains aggregated data" warning when the metric is aggregated', () => {
    const wrapper = mountContent(true)
    expect(wrapper.findComponent(CircleAlert).exists()).toBe(true)
  })

  it('hides the warning when the metric is full-resolution', () => {
    const wrapper = mountContent(false)
    expect(wrapper.findComponent(CircleAlert).exists()).toBe(false)
  })
})
