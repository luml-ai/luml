import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import AlertBannerList from './AlertBannerList.vue'
import { Severity, type AlertBanner } from '@/api/types'
import { makeAlerts } from '@/test/fixtures'

const BANNERS = makeAlerts().groups.flatMap((group) => group.alerts)

function manyBanners(count: number): AlertBanner[] {
  return Array.from({ length: count }, (_, index) => ({
    ...BANNERS[0],
    metric: `feature_drift:f${index}`,
    feature: `f${index}`,
    severity: Severity.WARNING,
  }))
}

function mountList(banners: AlertBanner[], inspectable = false) {
  return mount(AlertBannerList, {
    props: { banners, inspectable },
    // the drawer teleports to the body; keep it inline so assertions stay on the wrapper
    global: { stubs: { apexchart: true, teleport: true } },
  })
}

describe('AlertBannerList', () => {
  it('stays a plain summary unless the section asks for inspection', async () => {
    const wrapper = mountList(BANNERS)

    await wrapper.findAll('[data-testid="alert-banner"]')[0].trigger('click')

    expect(wrapper.find('[data-testid="alert-drawer"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="alert-banner"]').element.tagName).toBe('DIV')
  })

  it('scrolls past ten rows instead of pushing the section off the page', () => {
    expect(mountList(manyBanners(10)).find('.scroll').classes()).not.toContain('scrollable')
    expect(mountList(manyBanners(11)).find('.scroll').classes()).toContain('scrollable')
  })

  it('opens the alert in the same sidebar the Alerts tab uses', async () => {
    const wrapper = mountList(BANNERS, true)

    const banner = wrapper.findAll('[data-testid="alert-banner"]')[0]
    expect(banner.element.tagName).toBe('BUTTON')
    await banner.trigger('click')

    const drawer = wrapper.find('[data-testid="alert-drawer"]')
    expect(drawer.text()).toContain('income')
    expect(drawer.find('[data-testid="alert-timing"]').exists()).toBe(true)
    expect(drawer.find('[data-testid="alert-history"]').exists()).toBe(true)
  })

  it('passes a follow-the-feature request up to the dashboard', async () => {
    const wrapper = mountList(BANNERS, true)
    await wrapper.findAll('[data-testid="alert-banner"]')[0].trigger('click')

    await wrapper.find('[data-testid="alert-show-feature"]').trigger('click')

    expect(wrapper.emitted('show-feature')?.[0]).toEqual([
      expect.objectContaining({ feature: 'income' }),
    ])
    expect(wrapper.find('[data-testid="alert-drawer"]').exists()).toBe(false)
  })

  it('hides acknowledged banners: a seen alert belongs to the Alerts tab only', () => {
    const acknowledged = [{ ...BANNERS[0], state: 'acknowledged' }, BANNERS[1]]
    const wrapper = mountList(acknowledged, true)

    const banners = wrapper.findAll('[data-testid="alert-banner"]')
    expect(banners).toHaveLength(1)
    expect(banners[0].text()).not.toContain(BANNERS[0].feature ?? '@@none@@')
  })

  it('renders nothing at all when every alert has been seen', () => {
    const allSeen = BANNERS.map((banner) => ({ ...banner, state: 'acknowledged' }))
    const wrapper = mountList(allSeen, true)

    expect(wrapper.find('[data-testid="alert-banners"]').exists()).toBe(false)
  })

  it('closes the panel when its alert is gone from the reloaded list', async () => {
    const wrapper = mountList(BANNERS, true)
    await wrapper.findAll('[data-testid="alert-banner"]')[0].trigger('click')
    expect(wrapper.find('[data-testid="alert-drawer"]').exists()).toBe(true)

    await wrapper.setProps({ banners: BANNERS.slice(1) })

    expect(wrapper.find('[data-testid="alert-drawer"]').exists()).toBe(false)
  })
})
