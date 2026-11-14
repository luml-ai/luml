import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import MetricCard from './MetricCard.vue'
import type { Card } from '@/api/types'

const FEATURES = [
  'prompt_tokens',
  'context_tokens',
  'output_tokens',
  'history_turns',
  'message_chars',
  'temperature',
]

function driftCard(featureNames: string[]): Card {
  return {
    key: 'drifted_features',
    label: 'Drifted features',
    value: featureNames.length,
    feature_names: featureNames,
  } as Card
}

describe('MetricCard — drifted features', () => {
  it('previews two features and counts the rest', () => {
    const wrapper = mount(MetricCard, { props: { card: driftCard(FEATURES) } })

    const chips = wrapper.findAll('.feature').map((chip) => chip.text())
    expect(chips).toEqual(['prompt_tokens', 'context_tokens'])
    expect(wrapper.get('[data-testid="drifted-more"]').text()).toBe('+4')
  })

  it('opens the full list on demand and closes it again', async () => {
    // the list is teleported to the body so nothing on the page can paint over it
    const wrapper = mount(MetricCard, {
      props: { card: driftCard(FEATURES) },
      global: { stubs: { teleport: true } },
    })

    expect(wrapper.find('[data-testid="drifted-popover"]').exists()).toBe(false)

    await wrapper.get('[data-testid="drifted-more"]').trigger('click')
    const popover = wrapper.get('[data-testid="drifted-popover"]')
    expect(popover.findAll('li')).toHaveLength(FEATURES.length)
    expect(popover.text()).toContain('temperature')

    await wrapper.get('[data-testid="drifted-more"]').trigger('click')
    expect(wrapper.find('[data-testid="drifted-popover"]').exists()).toBe(false)
  })

  it('renders the open list outside the card, on the body', async () => {
    const wrapper = mount(MetricCard, {
      props: { card: driftCard(FEATURES) },
      attachTo: document.body,
    })

    await wrapper.get('[data-testid="drifted-more"]').trigger('click')

    const popover = document.body.querySelector('[data-testid="drifted-popover"]')
    expect(popover).not.toBeNull()
    expect(wrapper.element.contains(popover)).toBe(false)
    expect((popover as HTMLElement).style.position).toBe('fixed')

    wrapper.unmount()
  })

  it('shows no disclosure when everything fits', () => {
    const wrapper = mount(MetricCard, { props: { card: driftCard(['temperature', 'top_p']) } })

    expect(wrapper.findAll('.feature')).toHaveLength(2)
    expect(wrapper.find('[data-testid="drifted-more"]').exists()).toBe(false)
  })

  it('says none when nothing drifted', () => {
    const wrapper = mount(MetricCard, { props: { card: driftCard([]) } })

    expect(wrapper.get('[data-testid="drifted-features-detail"]').text()).toBe('none')
  })

  it('leaves other cards on the plain detail line', () => {
    const card = {
      key: 'active_alerts',
      label: 'Active alerts',
      value: 4,
      critical_count: 2,
    } as Card

    const wrapper = mount(MetricCard, { props: { card } })

    expect(wrapper.find('[data-testid="drifted-features-detail"]').exists()).toBe(false)
    expect(wrapper.get('.detail').text()).toBe('2 critical')
  })
})
