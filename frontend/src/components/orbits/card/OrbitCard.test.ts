import { mount } from '@vue/test-utils'
import { describe, it, expect, vi } from 'vitest'
import OrbitCard from './OrbitCard.vue'
import { OrbitRoleEnum } from '../orbits.interfaces'
import { PermissionEnum } from '@/lib/api/DataforceApi.interfaces'

const mockData = {
  id: 1,
  name: 'Test Orbit',
  organization_id: 1,
  total_members: 10,
  created_at: new Date(),
  updated_at: null,
  bucket_secret_id: 0,
  total_collections: 5,
  role: OrbitRoleEnum.member,
  permissions: {
    orbit: PermissionEnum.read,
    orbit_user: PermissionEnum.read,
    model: PermissionEnum.create,
    collection: PermissionEnum.create,
  },
}

describe('OrbitCard', () => {
  it('renders default card with data', () => {
    const wrapper = mount(OrbitCard, {
      props: { type: 'default', data: mockData, manageAvailable: true },
      global: {
        stubs: ['Orbit', 'EllipsisVertical', 'Button', 'OrbitEditor'],
        mocks: {
          $router: { push: vi.fn() },
        },
      },
    })

    expect(wrapper.find('.title span').text()).toBe('Test Orbit')
    expect(wrapper.text()).toContain('Number of collections: 5')
    expect(wrapper.text()).toContain('Number of Members: 10')
  })

  it('renders create card with manageAvailable = true', () => {
    const wrapper = mount(OrbitCard, {
      props: { type: 'create', manageAvailable: true },
      global: {
        stubs: ['Plus', 'Button'],
      },
    })

    expect(wrapper.text()).toContain('Add new Orbit')
    expect(wrapper.findComponent({ name: 'Button' }).exists()).toBe(true)
  })

  it('renders create card with manageAvailable = false', () => {
    const wrapper = mount(OrbitCard, {
      props: { type: 'create', manageAvailable: false },
      global: {
        stubs: ['Lock'],
      },
    })

    expect(wrapper.text()).toContain('No Orbits available')
    expect(wrapper.text()).toContain('Ask your admin to create one')
  })

  it('emits createNew event on button click in create mode', async () => {
    const wrapper = mount(OrbitCard, {
      props: { type: 'create', manageAvailable: true },
      global: {
        stubs: ['Plus', 'Button'],
      },
    })

    await wrapper.findComponent({ name: 'Button' }).trigger('click')
    expect(wrapper.emitted()).toHaveProperty('createNew')
  })
})
