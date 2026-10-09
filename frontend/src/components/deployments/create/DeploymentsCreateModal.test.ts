import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
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

const modelSettingsStub = {
  name: 'DeploymentsFormModelSettings',
  props: ['modelId'],
  emits: ['update:modelId', 'modelChanged'],
  template: '<div />',
}

const satelliteSettingsStub = {
  name: 'DeploymentsFormSatelliteSettings',
  props: ['fields', 'satelliteId'],
  emits: ['update:fields', 'update:satelliteId'],
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
        DeploymentsFormModelSettings: modelSettingsStub,
        DeploymentsFormSatelliteSettings: satelliteSettingsStub,
      },
    },
  })
}

async function submitWithFields(fields: Record<string, unknown>[]) {
  const wrapper = mountModal()
  const modelSettings = wrapper.getComponent(modelSettingsStub)
  modelSettings.vm.$emit('update:modelId', 'model-1')
  await nextTick()
  modelSettings.vm.$emit('modelChanged', { id: 'model-1' })
  const settings = wrapper.getComponent(satelliteSettingsStub)
  settings.vm.$emit('update:satelliteId', 'satellite-1')
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

function mountModalWithModelSettings() {
  return mount(DeploymentsCreateModal, {
    props: { visible: true },
    global: {
      stubs: {
        Dialog: { template: '<div><slot name="header" /><slot /></div>' },
        Form: {
          name: 'Form',
          data: () => ({ valid: true }),
          template: '<form><slot /></form>',
        },
        Button: {
          props: ['label', 'disabled'],
          template: '<button :disabled="disabled">{{ label }}</button>',
        },
        DeploymentsFormBasicsSettings: true,
        DeploymentsFormModelSettings: {
          name: 'DeploymentsFormModelSettings',
          props: ['modelId'],
          template: '<div />',
        },
        DeploymentsFormSatelliteSettings: {
          name: 'DeploymentsFormSatelliteSettings',
          props: ['satelliteId', 'fields', 'monitoringEnabled', 'selectedModel'],
          template: '<div />',
        },
      },
    },
  })
}

describe('DeploymentsCreateModal', () => {
  it('clears the satellite and disables Deploy when the model changes', async () => {
    const wrapper = mountModalWithModelSettings()
    const modelSettings = wrapper.getComponent({ name: 'DeploymentsFormModelSettings' })
    const satelliteSettings = wrapper.getComponent({ name: 'DeploymentsFormSatelliteSettings' })
    const deployButton = () => wrapper.get('button[type="submit"]')

    modelSettings.vm.$emit('update:modelId', 'model-a')
    await nextTick()
    modelSettings.vm.$emit('model-changed', { id: 'model-a' })
    satelliteSettings.vm.$emit('update:satelliteId', 'satellite-a')
    satelliteSettings.vm.$emit('update:fields', [{ key: 'field', value: 'old-value' }])
    satelliteSettings.vm.$emit('update:monitoringEnabled', true)
    await nextTick()

    expect(satelliteSettings.props('satelliteId')).toBe('satellite-a')
    expect(deployButton().attributes('disabled')).toBeUndefined()

    modelSettings.vm.$emit('update:modelId', 'model-b')
    await nextTick()

    expect(satelliteSettings.props('satelliteId')).toBe('')
    expect(satelliteSettings.props('fields')).toEqual([])
    expect(satelliteSettings.props('monitoringEnabled')).toBe(false)
    expect(satelliteSettings.props('selectedModel')).toBeNull()
    expect(deployButton().attributes('disabled')).toBeDefined()

    wrapper.unmount()
  })
})
