import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SecretsEditor from './SecretsEditor.vue'
import type { OrbitSecret } from '@/lib/api/orbit-secrets/interfaces'

const mocks = vi.hoisted(() => ({
  deleteSecret: vi.fn(),
  getSecretById: vi.fn(),
  toastAdd: vi.fn(),
}))

vi.mock('@/stores/orbit-secrets', () => ({
  useSecretsStore: () => ({
    deleteSecret: mocks.deleteSecret,
    getSecretById: mocks.getSecretById,
    updateSecret: vi.fn(),
    existingTags: [],
  }),
}))

vi.mock('@/stores/orbits', () => ({
  useOrbitsStore: () => ({
    currentOrbitDetails: { id: 'orbit-1', organization_id: 'org-1' },
  }),
}))

vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: mocks.toastAdd }),
  useConfirm: () => ({ require: (options: { accept: () => void }) => options.accept() }),
}))

const secret: OrbitSecret = {
  id: 'secret-1',
  name: 'OPENAI_API_KEY',
  value: '',
  orbit_id: 'orbit-1',
  created_at: '2026-10-03T00:00:00Z',
  tags: [],
}

function mountEditor() {
  return mount(SecretsEditor, {
    props: { visible: true, secret },
    global: {
      stubs: {
        UiDialogRight: {
          props: ['footerActions'],
          template:
            '<div><slot /><button data-testid="delete" @click="footerActions.leftButton.props.onClick()" /></div>',
        },
        Form: { template: '<form><slot /></form>' },
        InputText: true,
        Password: true,
        AutoComplete: true,
      },
    },
  })
}

describe('SecretsEditor deletion', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getSecretById.mockResolvedValue({ ...secret, value: 'sk-1' })
  })

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
