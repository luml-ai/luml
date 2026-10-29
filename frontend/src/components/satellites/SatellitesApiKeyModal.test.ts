import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PrimeVue from 'primevue/config'
import SatellitesApiKeyModal from './SatellitesApiKeyModal.vue'

const { regenerateApiKey, addToast, writeText } = vi.hoisted(() => ({
  regenerateApiKey: vi.fn(),
  addToast: vi.fn(),
  writeText: vi.fn(),
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

const firstKey = 'dfssat_first-test-key-0123456789'
const secondKey = 'dfssat_second-test-key-9876543210'

function mountModal(apiKey: string | null = null) {
  return mount(SatellitesApiKeyModal, {
    props: { apiKey, satelliteId: 'satellite-1', visible: true },
    global: {
      plugins: [PrimeVue],
      stubs: {
        Dialog: {
          props: ['visible'],
          template: '<div v-if="visible"><slot /><slot name="footer" /></div>',
        },
      },
    },
  })
}

describe('SatellitesApiKeyModal', () => {
  let wrapper: ReturnType<typeof mountModal>

  beforeEach(() => {
    regenerateApiKey.mockReset().mockResolvedValue({ key: firstKey })
    addToast.mockReset()
    writeText.mockReset().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    vi.useFakeTimers()
    wrapper = mountModal()
  })

  afterEach(() => {
    wrapper.unmount()
    vi.clearAllTimers()
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('shows the current satellite prefix when the full key is unavailable', () => {
    expect(wrapper.get('input').element.value).toBe(
      'dfssat_***************************************',
    )
    expect(wrapper.get('input').attributes('disabled')).toBeDefined()
    expect(wrapper.get('button').text()).toBe('Regenerate key')
  })

  it('keeps the regenerated key and regeneration available when reopened', async () => {
    await wrapper.get('button').trigger('click')
    await flushPromises()
    await wrapper.setProps({ visible: false })
    await wrapper.setProps({ visible: true })

    expect(regenerateApiKey).toHaveBeenCalledExactlyOnceWith(
      'organization-1',
      'orbit-1',
      'satellite-1',
    )
    expect(wrapper.get('input').element.value).toBe('dfssat_fir*******************0123456789')
    const buttons = wrapper.findAll('button')
    expect(buttons.map((button) => button.text())).toContain('Regenerate key')
    await buttons[0].trigger('click')
    expect(writeText).toHaveBeenCalledExactlyOnceWith(firstKey)

    regenerateApiKey.mockResolvedValueOnce({ key: secondKey })
    await wrapper.get('button[aria-label="Regenerate key"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('input').element.value).toBe('dfssat_sec*******************9876543210')
    await wrapper.findAll('button')[0].trigger('click')
    expect(writeText).toHaveBeenLastCalledWith(secondKey)
    expect(wrapper.findAll('button').map((button) => button.text())).toContain('Regenerate key')
  })

  it('allows regenerating a key supplied after satellite creation', async () => {
    await wrapper.setProps({ apiKey: firstKey })

    const button = wrapper.get('button[aria-label="Regenerate key"]')
    regenerateApiKey.mockResolvedValueOnce({ key: secondKey })
    await button.trigger('click')
    await flushPromises()

    expect(wrapper.get('input').element.value).toBe('dfssat_sec*******************9876543210')
  })

  it('disables regeneration while pending and preserves the previous key after failure', async () => {
    await wrapper.setProps({ apiKey: firstKey })
    let rejectRegeneration!: (error: Error) => void
    regenerateApiKey.mockReturnValueOnce(
      new Promise((_, reject) => {
        rejectRegeneration = reject
      }),
    )
    const button = wrapper.get('button[aria-label="Regenerate key"]')
    await button.trigger('click')

    expect(button.attributes('disabled')).toBeDefined()
    rejectRegeneration(new Error('Regeneration failed'))
    await flushPromises()

    expect(wrapper.get('input').element.value).toBe('dfssat_fir*******************0123456789')
    expect(button.attributes('disabled')).toBeUndefined()
    expect(addToast).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({ severity: 'error', detail: 'Failed to generate API Key' }),
    )
    await button.trigger('click')
    await flushPromises()

    expect(regenerateApiKey).toHaveBeenCalledTimes(2)
    expect(wrapper.get('input').element.value).toBe('dfssat_fir*******************0123456789')
  })
})
