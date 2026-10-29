import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PrimeVue from 'primevue/config'
import { Dialog } from 'primevue'
import SatellitesApiKeyModal from './SatellitesApiKeyModal.vue'

const { regenerateApiKey, addToast } = vi.hoisted(() => ({
  regenerateApiKey: vi.fn(),
  addToast: vi.fn(),
}))

vi.mock('@/stores/satellites', () => ({
  useSatellitesStore: () => ({ regenerateApiKey }),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { organizationId: 'organization-1', id: 'orbit-1' } }),
}))

vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: addToast }),
}))

enableAutoUnmount(afterEach)

function mountModal(apiKey: string | null = null) {
  return mount(SatellitesApiKeyModal, {
    props: { apiKey, satelliteId: 'satellite-1', visible: true },
    global: {
      plugins: [PrimeVue],
      stubs: {
        Dialog: { props: ['header'], template: '<div><slot /><slot name="footer" /></div>' },
      },
    },
  })
}

describe('SatellitesApiKeyModal', () => {
  beforeEach(() => {
    regenerateApiKey.mockReset().mockResolvedValue({ key: 'test-satellite-key' })
    vi.stubGlobal('navigator', { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('uses the existing satellite header and correct API key placeholder', () => {
    const wrapper = mountModal()

    expect(wrapper.getComponent(Dialog).props('header')).toBe('Satellite API key')
    expect(wrapper.get('input').attributes('placeholder')).toBe('API key')
  })

  it('preserves the connection header and supplied key for a newly created satellite', async () => {
    const wrapper = mountModal('test-initial-key')

    expect(wrapper.getComponent(Dialog).props('header')).toBe('Connect a new satellite')
    expect(wrapper.get('input').element.value).toBe('test-initial-key')
    await wrapper.get('button').trigger('click')
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('test-initial-key')
  })

  it('discards a regenerated key and copy feedback when closed and reopened', async () => {
    const wrapper = mountModal()
    await wrapper.get('button').trigger('click')
    await flushPromises()
    await wrapper.get('button').trigger('click')
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith('test-satellite-key')

    await wrapper.setProps({ visible: false })
    await wrapper.setProps({ visible: true })

    expect(wrapper.get('input').attributes('disabled')).toBeDefined()
    expect(wrapper.get('input').element.value).not.toContain('test-satellite-key')
    expect(wrapper.text()).toContain('For security reasons, this key is no longer visible.')
    expect(wrapper.get('button').text()).toBe('Regenerate key')
    expect(wrapper.find('.lucide-copy-check').exists()).toBe(false)
    expect(navigator.clipboard.writeText).toHaveBeenCalledTimes(1)
  })

  it('discards a key returned after close and reopen', async () => {
    let resolveKey!: (value: { key: string }) => void
    regenerateApiKey.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveKey = resolve
      }),
    )
    const wrapper = mountModal()
    await wrapper.get('button').trigger('click')
    await wrapper.setProps({ visible: false })
    await wrapper.setProps({ visible: true })

    resolveKey({ key: 'outdated-test-key' })
    await flushPromises()

    expect(wrapper.get('input').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('For security reasons, this key is no longer visible.')
    expect(addToast).not.toHaveBeenCalled()
    expect(navigator.clipboard.writeText).not.toHaveBeenCalled()
  })

  it('allows retry after regeneration fails', async () => {
    regenerateApiKey.mockRejectedValueOnce(new Error('Failed'))
    const wrapper = mountModal()
    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(addToast).toHaveBeenCalledWith(expect.objectContaining({ severity: 'error' }))
    expect(wrapper.get('input').attributes('disabled')).toBeDefined()
    await wrapper.get('button').trigger('click')
    await flushPromises()
    expect(wrapper.get('input').element.value).toBe('test-satellite-key')
  })
})
