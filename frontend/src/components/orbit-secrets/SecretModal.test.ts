import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SecretModal from './SecretModal.vue'
import { SECRET_MASK } from './secretMask'
import type { OrbitSecret } from '@/lib/api/orbit-secrets/interfaces'

const mocks = vi.hoisted(() => ({
  getSecretById: vi.fn(),
  toastAdd: vi.fn(),
}))

vi.mock('@/stores/orbit-secrets', () => ({
  useSecretsStore: () => ({ getSecretById: mocks.getSecretById }),
}))

vi.mock('@/stores/orbits', () => ({
  useOrbitsStore: () => ({
    currentOrbitDetails: { id: 'orbit-1', organization_id: 'org-1' },
  }),
}))

vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: mocks.toastAdd }),
}))

const secret: OrbitSecret = {
  id: 'secret-1',
  name: 'OPENAI_API_KEY',
  value: '',
  orbit_id: 'orbit-1',
  created_at: '2026-10-03T00:00:00Z',
  tags: [],
}

async function mountModal() {
  const wrapper = mount(SecretModal, {
    props: { secret, visible: false },
    global: {
      stubs: {
        Dialog: { template: '<div><slot /></div>' },
        InputGroup: { template: '<div><slot /></div>' },
        InputGroupAddon: { template: '<div><slot /></div>' },
        InputText: { props: ['value'], template: '<input data-testid="key" :value="value" />' },
        Button: {
          props: ['disabled'],
          template: '<button data-testid="copy" :disabled="disabled"><slot /></button>',
        },
      },
    },
  })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}

describe('SecretModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows a mask and disables copying when the backend returns an empty value', async () => {
    mocks.getSecretById.mockResolvedValue({ ...secret, value: '' })
    const wrapper = await mountModal()

    expect(mocks.getSecretById).toHaveBeenCalledWith('org-1', 'orbit-1', 'secret-1')
    expect(wrapper.get<HTMLInputElement>('[data-testid="key"]').element.value).toBe(SECRET_MASK)
    expect(wrapper.get<HTMLButtonElement>('[data-testid="copy"]').element.disabled).toBe(true)
  })

  it('shows the value and enables copying when the backend returns one', async () => {
    mocks.getSecretById.mockResolvedValue({ ...secret, value: 'sk-1' })
    const wrapper = await mountModal()

    expect(wrapper.get<HTMLInputElement>('[data-testid="key"]').element.value).toBe('sk-1')
    expect(wrapper.get<HTMLButtonElement>('[data-testid="copy"]').element.disabled).toBe(false)
  })
})
