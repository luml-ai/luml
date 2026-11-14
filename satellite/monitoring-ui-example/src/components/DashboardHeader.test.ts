import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import DashboardHeader from './DashboardHeader.vue'
import { makeHeader } from '@/test/fixtures'

describe('DashboardHeader', () => {
  it('shows only the name and status, no meta line and no inference URL', () => {
    const wrapper = mount(DashboardHeader, {
      props: {
        header: makeHeader({
          last_prediction_at: '2026-07-07T12:00:00Z',
          last_monitored_at: '2026-07-05T09:00:00Z',
        }),
      },
    })

    expect(wrapper.find('[data-testid="deployment-name"]').exists()).toBe(true)
    expect(wrapper.text()).not.toContain('last prediction')
    expect(wrapper.text()).not.toContain('last monitored')
    expect(wrapper.find('[data-testid="inference-url"]').exists()).toBe(false)
  })
})
