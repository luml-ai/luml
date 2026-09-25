import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import DeploymentsCreateModal from './DeploymentsCreateModal.vue'

vi.mock('@/stores/collections', () => ({
  useCollectionsStore: () => ({ requestInfo: { organizationId: 'org-1', orbitId: 'orbit-1' } }),
}))

vi.mock('@/stores/deployments', () => ({
  useDeploymentsStore: () => ({ createDeployment: vi.fn() }),
}))

vi.mock('primevue', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>
  return { ...actual, useToast: () => ({ add: vi.fn() }) }
})

function mountModal() {
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
    const wrapper = mountModal()
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
