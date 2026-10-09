import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
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
      directives: { tooltip: () => undefined },
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

  it('shows the kit kind before the slug', () => {
    const wrapper = mountCard(
      satellite({
        kit_info: {
          name: 'luml-satellite',
          version: '1.2.3',
          kind: 'kubernetes',
          api_version: 1,
        },
      }),
    )

    expect(wrapper.get('[data-testid="satellite-kind-slug"]').text()).toBe(
      'kubernetes · edge-cluster',
    )
  })

  it('keeps the old slug display when kit information is absent', () => {
    const wrapper = mountCard(satellite())

    expect(wrapper.find('[data-testid="satellite-kind-slug"]').exists()).toBe(false)
    expect(wrapper.get('.slug').text()).toBe('edge-cluster')
  })
})
