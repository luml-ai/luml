import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { CircleAlert } from 'lucide-vue-next'
import DynamicMetricsItemContent from '../DynamicMetricsItemContent.vue'

function mountContent(aggregationSteps: number | null, loading = false) {
  const tooltips: unknown[] = []
  const wrapper = mount(DynamicMetricsItemContent, {
    props: { title: 'loss', loading, aggregationSteps },
    slots: { default: '<div data-testid="chart" />' },
    global: {
      directives: {
        tooltip: { mounted: (_element: HTMLElement, binding) => tooltips.push(binding.value) },
      },
      stubs: {
        UiScalable: { template: '<div><slot /></div>' },
        Button: true,
        ProgressSpinner: true,
      },
    },
  })
  return { wrapper, tooltips }
}

describe('DynamicMetricsItemContent aggregated warning', () => {
  it('explains the aggregation when the data on screen is aggregated', () => {
    const { wrapper, tooltips } = mountContent(4096)
    expect(wrapper.findComponent(CircleAlert).exists()).toBe(true)
    expect(tooltips).toEqual([
      'Each point is an average over up to 4,096 steps. Zoom in to see more detail.',
    ])
  })

  it('hides the warning when every point is one logged value', () => {
    const { wrapper } = mountContent(null)
    expect(wrapper.findComponent(CircleAlert).exists()).toBe(false)
  })
})

describe('DynamicMetricsItemContent loading', () => {
  it('keeps the chart and the fullscreen button while loading and shows a small spinner', () => {
    const { wrapper } = mountContent(16, true)
    expect(wrapper.find('[data-testid="chart"]').exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'Button' }).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'ProgressSpinner' }).exists()).toBe(true)
  })

  it('shows no spinner once loaded', () => {
    const { wrapper } = mountContent(16, false)
    expect(wrapper.findComponent({ name: 'ProgressSpinner' }).exists()).toBe(false)
  })
})
