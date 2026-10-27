import { flushPromises, mount, shallowMount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import DeploymentsFormModelSettings from './DeploymentsFormModelSettings.vue'
import { defineComponent, ref } from 'vue'
import { Form } from '@primevue/forms'
import PrimeVue from 'primevue/config'
import { getInitialFormData } from '../../deployments.const'
import { createDeploymentResolver } from '@/utils/forms/resolvers'

const harness = vi.hoisted(() => ({
  getArtifact: vi.fn(),
}))

vi.mock('@/stores/artifacts', () => ({
  useArtifactsStore: () => ({ getArtifact: harness.getArtifact }),
}))
vi.mock('@/stores/collections', () => ({
  useCollectionsStore: () => ({ requestInfo: { organizationId: 'org-1', orbitId: 'orbit-1' } }),
}))
vi.mock('@/stores/orbit-secrets', () => ({
  useSecretsStore: () => ({ loadSecrets: vi.fn().mockResolvedValue(undefined), secretsList: [] }),
}))
vi.mock('@/lib/fnnx/FnnxService', () => ({
  FnnxService: {
    getDynamicAttributes: (manifest: { attribute: string }) => ({
      secrets: [],
      notSecrets: [{ name: manifest.attribute }],
    }),
    getEnvVars: () => ({ secrets: [], notSecrets: [] }),
  },
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { organizationId: 'org-1', id: 'orbit-1' } }),
}))
vi.mock('primevue', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>
  return { ...actual, useToast: () => ({ add: vi.fn() }) }
})

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

function model(id: string) {
  return { id, manifest: { attribute: `${id}-attribute` } }
}

describe('DeploymentsFormModelSettings', () => {
  it('keeps the latest model when an earlier model request resolves last', async () => {
    const requestA = deferred<ReturnType<typeof model>>()
    const requestB = deferred<ReturnType<typeof model>>()
    harness.getArtifact.mockImplementation((id: string) =>
      id === 'model-a' ? requestA.promise : requestB.promise,
    )
    const wrapper = shallowMount(DeploymentsFormModelSettings, {
      props: { collectionId: 'collection-1', modelId: 'model-a' },
      global: { mocks: { $route: { params: { organizationId: 'org-1', id: 'orbit-1' } } } },
    })
    await flushPromises()

    await wrapper.setProps({ modelId: 'model-b' })
    requestB.resolve(model('model-b'))
    await flushPromises()
    requestA.resolve(model('model-a'))
    await flushPromises()

    expect(harness.getArtifact).toHaveBeenCalledTimes(2)
    const changedModels = wrapper.emitted('modelChanged')?.map(([emitted]) => emitted)
    expect(changedModels?.at(-1)).toEqual(model('model-b'))
    expect(changedModels).not.toContainEqual(model('model-a'))
    expect(wrapper.emitted('update:dynamicAttributes')?.at(-1)).toEqual([
      [{ key: 'model-b-attribute', label: 'model-b-attribute', value: null }],
    ])
  })
})

describe('DeploymentsFormModelSettings custom variable validation', () => {
  it('shows errors for an empty row on blur and clears them after correction', async () => {
    const wrapper = mount(
      defineComponent({
        components: { DeploymentForm: Form, DeploymentsFormModelSettings },
        setup() {
          const values = ref({
            ...getInitialFormData(),
            name: 'Deployment',
            collectionId: 'collection-1',
            modelId: 'model-1',
            satelliteId: 'satellite-1',
          })
          return { values, resolver: createDeploymentResolver(values) }
        },
        template: `
          <DeploymentForm ref="form" :initial-values="values" :resolver="resolver">
            <DeploymentsFormModelSettings v-model:custom-variables="values.customVariables" />
          </DeploymentForm>
        `,
      }),
      {
        global: {
          plugins: [PrimeVue],
          mocks: { $route: { params: { organizationId: 'org-1', id: 'orbit-1' } } },
          stubs: { CollectionSelect: true, ModelSelect: true, SecretsSelect: true },
        },
      },
    )
    await flushPromises()
    await wrapper.get('button').trigger('click')
    await wrapper.get('input[placeholder="Enter key"]').trigger('blur')
    await wrapper.get('input[placeholder="Enter value"]').trigger('blur')
    await flushPromises()

    const row = wrapper.get('.custom-variables__item')
    expect(row.findAll('[data-pc-name="message"]').map((message) => message.text())).toEqual([
      'Key is required',
      'Value is required',
    ])
    expect(row.get('input[placeholder="Enter key"]').attributes('aria-invalid')).toBe('true')
    expect(row.get('input[placeholder="Enter value"]').attributes('aria-invalid')).toBe('true')

    await row.get('input[placeholder="Enter key"]').setValue('LOG_LEVEL')
    await flushPromises()
    expect(row.findAll('[data-pc-name="message"]').map((message) => message.text())).toEqual([
      'Value is required',
    ])

    await row.get('input[placeholder="Enter value"]').setValue('debug')
    await flushPromises()

    expect(row.findAll('[data-pc-name="message"]')).toHaveLength(0)
    expect(wrapper.getComponent(Form).vm).toHaveProperty('valid', true)
    wrapper.unmount()
  })
})
