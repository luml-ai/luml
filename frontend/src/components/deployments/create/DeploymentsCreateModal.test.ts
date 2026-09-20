import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DeploymentsCreateModal from './DeploymentsCreateModal.vue'

const deploymentsStore = {
  createDeployment: vi.fn(),
}

vi.mock('@/stores/collections', () => ({
  useCollectionsStore: () => ({
    requestInfo: { organizationId: 'org-1', orbitId: 'orbit-1' },
  }),
}))

vi.mock('@/stores/deployments', () => ({
  useDeploymentsStore: () => deploymentsStore,
}))

vi.mock('primevue', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>
  return { ...actual, useToast: () => ({ add: vi.fn() }) }
})

const formStub = {
  name: 'Form',
  props: ['initialValues', 'resolver'],
  emits: ['submit'],
  template: '<form data-testid="deployment-form"><slot /></form>',
}

const satelliteSettingsStub = {
  name: 'DeploymentsFormSatelliteSettings',
  props: ['fields'],
  emits: ['update:fields'],
  template: '<button data-testid="seed-fields" @click="$emit(\'update:fields\', seededFields)" />',
  data: () => ({ seededFields: [] }),
}

function mountModal() {
  return mount(DeploymentsCreateModal, {
    props: { visible: true },
    global: {
      stubs: {
        Dialog: { template: '<div><slot name="header" /><slot /></div>' },
        Button: { props: ['label'], template: '<button>{{ label }}</button>' },
        Form: formStub,
        DeploymentsFormBasicsSettings: true,
        DeploymentsFormModelSettings: true,
        DeploymentsFormSatelliteSettings: satelliteSettingsStub,
      },
    },
  })
}

async function submitWithFields(fields: Record<string, unknown>[]) {
  const wrapper = mountModal()
  const settings = wrapper.getComponent(satelliteSettingsStub)
  settings.vm.seededFields = fields
  await settings.get('[data-testid="seed-fields"]').trigger('click')
  wrapper.getComponent(formStub).vm.$emit('submit', { valid: true })
  await flushPromises()
}

describe('DeploymentsCreateModal satellite parameters', () => {
  beforeEach(() => {
    deploymentsStore.createDeployment.mockReset()
    deploymentsStore.createDeployment.mockResolvedValue(undefined)
  })

  it('submits untouched defaults as flat scalar parameters', async () => {
    await submitWithFields([
      { key: 'replicas', value: 1 },
      { key: 'memory', value: '2Gi' },
      { key: 'use_gpu', value: false },
    ])

    expect(deploymentsStore.createDeployment).toHaveBeenCalledWith(
      'org-1',
      'orbit-1',
      expect.objectContaining({
        satellite_parameters: { replicas: 1, memory: '2Gi', use_gpu: false },
      }),
    )
  })

  it('omits an untouched field from an old declaration without a default', async () => {
    await submitWithFields([{ key: 'legacy_setting', value: null }])

    expect(deploymentsStore.createDeployment).toHaveBeenCalledWith(
      'org-1',
      'orbit-1',
      expect.objectContaining({ satellite_parameters: {} }),
    )
  })
})
