import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SecretsEditor from './SecretsEditor.vue'
import PrimeVue from 'primevue/config'
import type { OrbitSecret } from '@/lib/api/orbit-secrets/interfaces'

const mocks = vi.hoisted(() => ({
  deleteSecret: vi.fn(),
  getSecretById: vi.fn(),
  updateSecret: vi.fn(),
  toastAdd: vi.fn(),
  orbit: { id: 'orbit-1', organization_id: 'org-1' } as {
    id: string
    organization_id: string
  } | null,
}))

vi.mock('@/stores/orbit-secrets', () => ({
  useSecretsStore: () => ({
    deleteSecret: mocks.deleteSecret,
    getSecretById: mocks.getSecretById,
    updateSecret: mocks.updateSecret,
    existingTags: [],
  }),
}))

vi.mock('@/stores/orbits', () => ({
  useOrbitsStore: () => ({
    get currentOrbitDetails() {
      return mocks.orbit
    },
  }),
}))

vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: mocks.toastAdd }),
  useConfirm: () => ({ require: (options: { accept: () => void }) => options.accept() }),
}))

const secret: OrbitSecret = {
  id: 'secret-1',
  name: 'secret-a',
  value: '',
  orbit_id: 'orbit-1',
  created_at: '2026-10-03T00:00:00Z',
  tags: [],
}

function mountEditor(
  props: { visible?: boolean; secret?: OrbitSecret | null } = {},
  realForm = false,
) {
  return mount(SecretsEditor, {
    props: { visible: true, secret, ...props },
    global: {
      plugins: [PrimeVue],
      stubs: {
        UiDialogRight: {
          props: ['footerActions'],
          template:
            '<div><slot /><button data-testid="delete" @click="footerActions.leftButton.props.onClick()" /><button data-testid="save" :disabled="footerActions.rightButton.props.disabled" /></div>',
        },
        Form: realForm ? false : { name: 'Form', template: '<form><slot /></form>' },
        InputText: realForm
          ? false
          : { name: 'InputText', props: ['modelValue'], template: '<input />' },
        Password: realForm
          ? false
          : { name: 'Password', props: ['modelValue'], template: '<input />' },
        AutoComplete: realForm
          ? false
          : { name: 'AutoComplete', props: ['modelValue'], template: '<input />' },
      },
    },
  })
}

beforeEach(() => {
  vi.resetAllMocks()
  mocks.orbit = { id: 'orbit-1', organization_id: 'org-1' }
  mocks.getSecretById.mockResolvedValue({ ...secret, value: 'test-value-a' })
})

describe('SecretsEditor deletion', () => {
  it('shows the backend conflict that names the deployments and keeps the dialog open', async () => {
    mocks.deleteSecret.mockRejectedValue({
      response: {
        status: 409,
        data: {
          detail: 'Cannot delete secret that is used by deployments: llm prod, llm staging',
        },
      },
    })
    const wrapper = mountEditor()
    await flushPromises()

    await wrapper.get('[data-testid="delete"]').trigger('click')
    await flushPromises()

    expect(mocks.deleteSecret).toHaveBeenCalledWith('org-1', 'orbit-1', 'secret-1')
    expect(mocks.toastAdd).toHaveBeenCalledWith(
      expect.objectContaining({
        severity: 'error',
        detail: 'Cannot delete secret that is used by deployments: llm prod, llm staging',
      }),
    )
    expect(wrapper.emitted('update:visible')).toBeUndefined()
  })

  it('closes the dialog after a successful deletion', async () => {
    mocks.deleteSecret.mockResolvedValue(undefined)
    const wrapper = mountEditor()
    await flushPromises()

    await wrapper.get('[data-testid="delete"]').trigger('click')
    await flushPromises()

    expect(mocks.toastAdd).toHaveBeenCalledWith(expect.objectContaining({ severity: 'success' }))
    expect(wrapper.emitted('update:visible')).toEqual([[false]])
  })
})

const otherSecret: OrbitSecret = {
  ...secret,
  id: 'secret-2',
  name: 'secret-b',
  tags: ['tag-b'],
}

function pendingDetails() {
  let resolve!: (value: OrbitSecret | null) => void
  let reject!: (error: Error) => void
  const promise = new Promise<OrbitSecret | null>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

function expectEmptyForm(wrapper: ReturnType<typeof mountEditor>) {
  expect(wrapper.getComponent({ name: 'InputText' }).props('modelValue')).toBe('')
  expect(wrapper.getComponent({ name: 'Password' }).props('modelValue')).toBe('')
  expect(wrapper.getComponent({ name: 'AutoComplete' }).props('modelValue')).toEqual([])
  expect(wrapper.get('[data-testid="save"]').attributes('disabled')).toBeDefined()
}

async function submit(wrapper: ReturnType<typeof mountEditor>, valid = true) {
  wrapper.getComponent({ name: 'Form' }).vm.$emit('submit', { valid })
  await flushPromises()
}

describe('SecretsEditor detail loading', () => {
  it('saves loaded details through the real form without requiring a field edit', async () => {
    const wrapper = mountEditor({}, true)
    await flushPromises()
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mocks.updateSecret).toHaveBeenCalledExactlyOnceWith('org-1', 'orbit-1', {
      id: secret.id,
      name: secret.name,
      value: 'test-value-a',
      tags: [],
    })

    await wrapper.setProps({ visible: false })
    mocks.getSecretById.mockResolvedValue({ ...otherSecret, value: 'test-value-b' })
    await wrapper.setProps({ visible: true, secret: otherSecret })
    await flushPromises()
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mocks.updateSecret).toHaveBeenCalledTimes(2)
    expect(mocks.updateSecret).toHaveBeenLastCalledWith('org-1', 'orbit-1', {
      id: otherSecret.id,
      name: otherSecret.name,
      value: 'test-value-b',
      tags: ['tag-b'],
    })
  })

  it('loads once on initial open and saves the current details only after they load', async () => {
    const details = pendingDetails()
    mocks.getSecretById.mockReturnValue(details.promise)
    const wrapper = mountEditor()
    await flushPromises()

    expectEmptyForm(wrapper)
    await submit(wrapper)
    expect(mocks.updateSecret).not.toHaveBeenCalled()
    expect(mocks.getSecretById).toHaveBeenCalledExactlyOnceWith('org-1', 'orbit-1', secret.id)

    details.resolve({ ...secret, value: 'test-value-a', tags: ['tag-a'] })
    await flushPromises()
    expect(wrapper.get('[data-testid="save"]').attributes('disabled')).toBeUndefined()
    await submit(wrapper, false)
    expect(mocks.updateSecret).not.toHaveBeenCalled()
    await submit(wrapper)
    expect(mocks.updateSecret).toHaveBeenCalledExactlyOnceWith('org-1', 'orbit-1', {
      id: secret.id,
      name: secret.name,
      value: 'test-value-a',
      tags: ['tag-a'],
    })
  })

  it('clears the previous form when opening another secret and blocks saving while it loads', async () => {
    const wrapper = mountEditor({ visible: false, secret: null })
    await wrapper.setProps({ visible: true, secret })
    await flushPromises()
    expect(mocks.getSecretById).toHaveBeenCalledTimes(1)
    await wrapper.setProps({ visible: false })
    expectEmptyForm(wrapper)

    const details = pendingDetails()
    mocks.getSecretById.mockReturnValue(details.promise)
    await wrapper.setProps({ visible: true, secret: otherSecret })
    expectEmptyForm(wrapper)
    await submit(wrapper)
    expect(mocks.updateSecret).not.toHaveBeenCalled()
    expect(mocks.getSecretById).toHaveBeenCalledTimes(2)

    details.resolve({ ...otherSecret, value: 'test-value-b' })
    await flushPromises()
    await submit(wrapper)
    expect(mocks.updateSecret).toHaveBeenCalledExactlyOnceWith('org-1', 'orbit-1', {
      id: otherSecret.id,
      name: otherSecret.name,
      value: 'test-value-b',
      tags: ['tag-b'],
    })
  })

  it('keeps the form empty and Save blocked after the current request fails', async () => {
    const wrapper = mountEditor()
    await flushPromises()
    mocks.getSecretById.mockRejectedValue(new Error('load failed'))
    await wrapper.setProps({ secret: otherSecret })
    await flushPromises()

    expectEmptyForm(wrapper)
    await submit(wrapper)
    expect(mocks.updateSecret).not.toHaveBeenCalled()
    expect(mocks.toastAdd).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({ severity: 'error', detail: 'Failed to load secret details' }),
    )
  })

  it.each([null, { ...secret, value: 'test-value-a' }])(
    'blocks saving if details are missing or belong to a different secret',
    async (details) => {
      mocks.getSecretById.mockResolvedValue(details)
      const wrapper = mountEditor({ secret: otherSecret })
      await flushPromises()
      expectEmptyForm(wrapper)
      await submit(wrapper)
      expect(mocks.updateSecret).not.toHaveBeenCalled()
    },
  )

  it.each(['resolve', 'reject'] as const)(
    'ignores a stale request that later %ss after switching secrets',
    async (result) => {
      const stale = pendingDetails()
      mocks.getSecretById.mockReturnValueOnce(stale.promise)
      const wrapper = mountEditor()
      await flushPromises()
      mocks.getSecretById.mockResolvedValue({ ...otherSecret, value: 'test-value-b' })
      await wrapper.setProps({ secret: otherSecret })
      await flushPromises()

      if (result === 'resolve') stale.resolve({ ...secret, value: 'test-value-a' })
      else stale.reject(new Error('stale failure'))
      await flushPromises()
      expect(mocks.toastAdd).not.toHaveBeenCalled()
      await submit(wrapper)
      expect(mocks.updateSecret).toHaveBeenCalledExactlyOnceWith('org-1', 'orbit-1', {
        id: otherSecret.id,
        name: otherSecret.name,
        value: 'test-value-b',
        tags: ['tag-b'],
      })
    },
  )

  it('ignores details from a closed opening when the same secret is reopened', async () => {
    const stale = pendingDetails()
    const current = pendingDetails()
    mocks.getSecretById.mockReturnValueOnce(stale.promise).mockReturnValueOnce(current.promise)
    const wrapper = mountEditor()
    await flushPromises()
    await wrapper.setProps({ visible: false })
    expectEmptyForm(wrapper)
    await submit(wrapper)
    expect(mocks.updateSecret).not.toHaveBeenCalled()

    await wrapper.setProps({ visible: true })
    stale.resolve({ ...secret, value: 'old-test-value' })
    await flushPromises()
    expectEmptyForm(wrapper)
    expect(mocks.getSecretById).toHaveBeenCalledTimes(2)
    current.resolve({ ...secret, value: 'new-test-value' })
    await flushPromises()
    await submit(wrapper)
    expect(mocks.updateSecret).toHaveBeenCalledWith(
      'org-1',
      'orbit-1',
      expect.objectContaining({ id: secret.id, value: 'new-test-value' }),
    )
  })

  it('does not load while hidden or save without a selected secret', async () => {
    const wrapper = mountEditor({ visible: false })
    await flushPromises()
    expect(mocks.getSecretById).not.toHaveBeenCalled()
    await wrapper.setProps({ visible: true, secret: null })
    expectEmptyForm(wrapper)
    await submit(wrapper)
    expect(mocks.updateSecret).not.toHaveBeenCalled()
    expect(mocks.getSecretById).not.toHaveBeenCalled()
  })

  it('blocks saving when orbit details are missing', async () => {
    mocks.orbit = null
    const wrapper = mountEditor()
    await flushPromises()
    expectEmptyForm(wrapper)
    await submit(wrapper)
    expect(mocks.updateSecret).not.toHaveBeenCalled()
    expect(mocks.getSecretById).not.toHaveBeenCalled()
  })

  it('ignores request failures after unmounting', async () => {
    const details = pendingDetails()
    mocks.getSecretById.mockReturnValue(details.promise)
    const wrapper = mountEditor()
    await flushPromises()
    wrapper.unmount()
    details.reject(new Error('load failed after unmount'))
    await flushPromises()
    expect(mocks.toastAdd).not.toHaveBeenCalled()
  })
})
