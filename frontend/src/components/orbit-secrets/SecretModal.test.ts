import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
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

enableAutoUnmount(afterEach)

const secret: OrbitSecret = {
  id: 'secret-1',
  name: 'OPENAI_API_KEY',
  value: '',
  orbit_id: 'orbit-1',
  created_at: '2026-10-03T00:00:00Z',
  tags: [],
}

async function mountModal(visible = false) {
  const wrapper = mount(SecretModal, {
    props: { secret, visible },
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
    mocks.getSecretById.mockReset()
    mocks.toastAdd.mockReset()
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

  it('clears the value and disables copying on close', async () => {
    mocks.getSecretById.mockResolvedValue({ value: 'test-secret' })
    const wrapper = await mountModal()

    await wrapper.setProps({ visible: false })

    expect(wrapper.get<HTMLInputElement>('[data-testid="key"]').element.value).toBe(SECRET_MASK)
    expect(wrapper.get<HTMLButtonElement>('[data-testid="copy"]').element.disabled).toBe(true)
  })

  it('clears the previous value when a different secret fails to load', async () => {
    mocks.getSecretById.mockResolvedValueOnce({ value: 'test-secret' })
    const wrapper = await mountModal()
    mocks.getSecretById.mockRejectedValueOnce({ response: { status: 403 } })

    await wrapper.setProps({ secret: { ...secret, id: 'secret-2' } })
    await flushPromises()

    expect(mocks.getSecretById).toHaveBeenLastCalledWith('org-1', 'orbit-1', 'secret-2')
    expect(wrapper.get<HTMLInputElement>('[data-testid="key"]').element.value).toBe(SECRET_MASK)
    expect(wrapper.get<HTMLButtonElement>('[data-testid="copy"]').element.disabled).toBe(true)
    expect(mocks.toastAdd).toHaveBeenCalledWith(expect.objectContaining({ severity: 'error' }))
  })

  it('does not restore a value when its request completes after close and reopen', async () => {
    let resolveSecret!: (value: { value: string }) => void
    mocks.getSecretById.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveSecret = resolve
      }),
    )
    const wrapper = await mountModal()
    await wrapper.setProps({ visible: false })
    mocks.getSecretById.mockRejectedValueOnce({ response: { status: 403 } })
    await wrapper.setProps({ secret: { ...secret, id: 'secret-2' }, visible: true })
    await flushPromises()

    resolveSecret({ value: 'outdated-test-secret' })
    await flushPromises()

    expect(wrapper.get<HTMLInputElement>('[data-testid="key"]').element.value).toBe(SECRET_MASK)
    expect(wrapper.get<HTMLButtonElement>('[data-testid="copy"]').element.disabled).toBe(true)
  })

  it('ignores an outdated failure while a different secret is loading', async () => {
    let rejectSecret!: (reason: Error) => void
    mocks.getSecretById.mockReturnValueOnce(
      new Promise((_, reject) => {
        rejectSecret = reject
      }),
    )
    const wrapper = await mountModal()
    let resolveSecret!: (value: { value: string }) => void
    mocks.getSecretById.mockReturnValueOnce(
      new Promise((resolve) => {
        resolveSecret = resolve
      }),
    )
    await wrapper.setProps({ secret: { ...secret, id: 'secret-2' } })

    rejectSecret(new Error('Denied'))
    await flushPromises()

    expect(wrapper.get<HTMLInputElement>('[data-testid="key"]').element.value).toBe('Loading...')
    expect(mocks.toastAdd).not.toHaveBeenCalled()

    resolveSecret({ value: 'current-test-secret' })
    await flushPromises()
    expect(wrapper.get<HTMLInputElement>('[data-testid="key"]').element.value).toBe(
      'current-test-secret',
    )
  })

  it('loads the secret when mounted open', async () => {
    mocks.getSecretById.mockResolvedValue({ value: 'test-secret' })
    const wrapper = await mountModal(true)

    expect(wrapper.get<HTMLInputElement>('[data-testid="key"]').element.value).toBe('test-secret')
  })
})
