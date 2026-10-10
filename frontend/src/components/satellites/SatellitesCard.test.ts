import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { Activity, Rocket } from 'lucide-vue-next'
import { SatelliteStatusEnum, type Satellite } from '@/lib/api/satellites/interfaces'
import SatellitesCard from './SatellitesCard.vue'

function satellite(overrides: Partial<Satellite> = {}): Satellite {
  return {
    id: 'satellite-1',
    orbit_id: 'orbit-1',
    name: 'Satellite',
    description: '',
    base_url: 'https://sat.example.com',
    paired: true,
    capabilities: {},
    present_capabilities: [],
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    last_seen_at: '2026-01-01T00:00:00Z',
    status: SatelliteStatusEnum.active,
    slug: 'edge-cluster',
    ...overrides,
  }
}

function mountCard(data: Satellite) {
  return mount(SatellitesCard, {
    props: { data },
    global: {
      directives: {
        tooltip: (el: HTMLElement, binding: { value: string }) => {
          el.setAttribute('data-tooltip', binding.value)
        },
      },
      stubs: {
        Button: { template: '<button><slot name="icon" /></button>' },
        Menu: true,
        UiId: { props: ['id'], template: '<span>{{ id }}</span>' },
        SatellitesEditModal: true,
        SatellitesApiKeyModal: true,
      },
    },
  })
}

describe('SatellitesCard', () => {
  it('renders an active satellite without a public address', () => {
    const wrapper = mountCard(satellite({ base_url: null }))

    expect(wrapper.get('.title').text()).toContain('Satellite')
    expect(wrapper.get('.status').classes()).toContain('status--success')
  })

  it.each([
    ['docker', 'docker-2026.01-v2-debian12'],
    ['kubernetes', 'kubernetes-2026.01-v1'],
    ['kubernetes', 'edge-cluster'],
  ])('shows only the slug for a %s satellite with slug %s', (kind, slug) => {
    const wrapper = mountCard(
      satellite({
        kit_info: {
          name: 'luml-satellite',
          version: '1.2.3',
          kind,
          api_version: 1,
        },
        slug,
      }),
    )

    expect(wrapper.get('.slug').text()).toBe(slug)
  })

  it('keeps the old slug display when kit information is absent', () => {
    const wrapper = mountCard(satellite())

    expect(wrapper.get('.slug').text()).toBe('edge-cluster')
  })

  it('omits the slug when absent even with kit information', () => {
    const wrapper = mountCard(
      satellite({
        slug: undefined,
        kit_info: {
          name: 'luml-satellite',
          version: '1.2.3',
          kind: 'kubernetes',
          api_version: 1,
        },
      }),
    )

    expect(wrapper.find('.slug').exists()).toBe(false)
  })

  it('shows deploy and monitoring icons with tooltips when both are reported', () => {
    const wrapper = mountCard(satellite({ present_capabilities: ['deploy', 'monitoring'] }))

    expect(wrapper.getComponent(Rocket).attributes('data-tooltip')).toBe('Deploy')
    expect(wrapper.getComponent(Activity).attributes('data-tooltip')).toBe('Monitoring')
    expect(wrapper.get('.capabilities').findAll('svg')).toHaveLength(2)
  })

  it('shows only the deploy icon when monitoring is not reported', () => {
    const wrapper = mountCard(satellite({ present_capabilities: ['deploy'] }))

    expect(wrapper.findComponent(Rocket).exists()).toBe(true)
    expect(wrapper.findComponent(Activity).exists()).toBe(false)
    expect(wrapper.get('.capabilities').findAll('svg')).toHaveLength(1)
  })

  it('shows monitoring without deploy when only monitoring is reported', () => {
    const wrapper = mountCard(satellite({ present_capabilities: ['monitoring'] }))

    expect(wrapper.findComponent(Rocket).exists()).toBe(false)
    expect(wrapper.findComponent(Activity).exists()).toBe(true)
  })

  it('does not show custom capabilities', () => {
    const wrapper = mountCard(
      satellite({
        capabilities: { 'custom.metrics': { version: 1 } },
        present_capabilities: ['custom.metrics'],
      }),
    )

    expect(wrapper.get('.capabilities').findAll('svg')).toHaveLength(0)
  })

  it('does not show capabilities that are not reported as present', () => {
    const wrapper = mountCard(
      satellite({
        capabilities: {
          deploy: {
            version: 1,
            api_versions: [1],
            facets: [],
            supported_variants: [],
            supported_tags_combinations: null,
            extra_fields_form_spec: [],
          },
          monitoring: { version: 1, api_versions: [1], facets: [], features: [] },
        },
      }),
    )

    expect(wrapper.get('.capabilities').findAll('svg')).toHaveLength(0)
  })
})
