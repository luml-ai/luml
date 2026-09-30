import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick, reactive } from 'vue'
import {
  DeploymentStatusEnum,
  MonitoringMode,
  type Deployment,
} from '@/lib/api/deployments/interfaces'
import { MonitoringFeature } from '@/lib/api/satellites/interfaces'
import { deploymentEditorResolver } from '@/utils/forms/resolvers'
import DeploymentsEditor from './DeploymentsEditor.vue'
import DeploymentsCreateModal from '../create/DeploymentsCreateModal.vue'

const TABULAR_KIND_TAG = 'luml.ai::kind_tabular:v1'
const TABULAR_MONITORING_TAG = 'luml.ai::tabular_monitoring:v1'

const monitoringCapability = {
  version: 1,
  api_versions: [1],
  facets: ['deployment:monitoring'],
  features: Object.values(MonitoringFeature),
}

const MONITORED = {
  id: 'sat-monitored',
  present_capabilities: ['deploy', 'monitoring'],
  capabilities: { monitoring: monitoringCapability },
}

const UNSUPPORTED_MONITORING = {
  id: 'sat-unsupported',
  present_capabilities: ['deploy'],
  capabilities: { monitoring: { ...monitoringCapability, api_versions: [9] } },
}

const satellitesStore = reactive({
  satellitesList: [MONITORED],
  loadSatellites: vi.fn(),
  setList: vi.fn(),
})

const artifactsStore = {
  getArtifact: vi.fn(),
}

const secretsStore = {
  secretsList: [],
  loadSecrets: vi.fn(async (): Promise<void> => undefined),
}

const dynamicAttributes = vi.hoisted(() => ({
  getDynamicAttributes: vi.fn(() => ({ secrets: [] as { name: string; description?: string }[] })),
}))

const deploymentsStore = {
  createDeployment: vi.fn(),
  update: vi.fn(),
  forceDeleteDeployment: vi.fn(),
}

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { organizationId: 'org-1' } }),
}))

vi.mock('@/stores/satellites', () => ({
  useSatellitesStore: () => satellitesStore,
}))

vi.mock('@/stores/artifacts', () => ({
  useArtifactsStore: () => artifactsStore,
}))

vi.mock('@/stores/orbit-secrets', () => ({
  useSecretsStore: () => secretsStore,
}))

vi.mock('@/stores/collections', () => ({
  useCollectionsStore: () => ({
    requestInfo: { organizationId: 'org-1', orbitId: 'orbit-1' },
  }),
}))

vi.mock('@/stores/deployments', () => ({
  useDeploymentsStore: () => deploymentsStore,
}))

vi.mock('@/lib/fnnx/FnnxService', () => ({
  FnnxService: dynamicAttributes,
}))

vi.mock('primevue', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>
  return { ...actual, useToast: () => ({ add: vi.fn() }) }
})

function deployment(satelliteId: string, monitoringMode = MonitoringMode.off): Deployment {
  return {
    id: 'deployment-1',
    orbit_id: 'orbit-1',
    satellite_id: satelliteId,
    artifact_id: 'artifact-1',
    status: DeploymentStatusEnum.active,
    monitoring_mode: monitoringMode,
    name: 'Deployment',
    description: '',
    tags: [],
    collection_id: 'collection-1',
    dynamic_attributes_secrets: {},
  } as unknown as Deployment
}

function modelWithTags(producerTags: string[]) {
  return {
    manifest: { producer_tags: producerTags },
  }
}

const nativeFormStub = {
  name: 'Form',
  props: ['initialValues', 'resolver'],
  emits: ['submit'],
  data: () => ({ valid: true }),
  template: '<form @submit.prevent="$emit(\'submit\', { valid })"><slot /></form>',
}

const buttonStub = {
  props: ['label', 'disabled'],
  template: '<button :disabled="disabled"><slot>{{ label }}</slot></button>',
}

const formStubs = {
  Dialog: {
    props: ['visible'],
    template: '<div><slot name="header" /><slot /><slot name="footer" /></div>',
  },
  Form: nativeFormStub,
  FormField: { template: '<div><slot /></div>' },
  DeploymentsFormBasicsSettings: true,
  DeploymentsFormModelSettings: true,
  DeploymentsFormSatelliteSettings: true,
  DeploymentsDelete: true,
  ForceDeleteConfirmDialog: true,
  SecretsSelect: true,
  Accordion: { template: '<div><slot /></div>' },
  AccordionPanel: { template: '<div><slot /></div>' },
  AccordionHeader: { template: '<div><slot /></div>' },
  AccordionContent: { template: '<div><slot /></div>' },
  ToggleSwitch: { template: '<button data-testid="editor-monitoring-toggle" />' },
  Button: buttonStub,
}

function mountEditor(data = deployment(MONITORED.id)) {
  return mount(DeploymentsEditor, {
    props: { data, visible: true },
    global: {
      stubs: {
        ...formStubs,
        ToggleSwitch: {
          name: 'ToggleSwitch',
          template: '<button data-testid="editor-monitoring-toggle" />',
        },
        Button: {
          props: ['label', 'disabled', 'loading'],
          template: '<button :disabled="disabled || loading"><slot>{{ label }}</slot></button>',
        },
      },
    },
  })
}

describe('DeploymentsEditor monitoring settings', () => {
  beforeEach(() => {
    satellitesStore.satellitesList = [MONITORED]
    artifactsStore.getArtifact.mockResolvedValue(
      modelWithTags([TABULAR_KIND_TAG, TABULAR_MONITORING_TAG]),
    )
  })

  it('shows the hint from the saved artifact and the satellite features', async () => {
    const wrapper = mountEditor()
    await flushPromises()

    const hint = wrapper.get('[data-testid="monitoring-sections-hint"]').text()
    expect(hint).toContain('Runtime, Traces, Alerts')
    expect(hint).toContain('Data quality')
    expect(hint).toContain('Output drift')
  })

  it('does not trust a raw monitoring declaration that is absent from present_capabilities', async () => {
    satellitesStore.satellitesList = [UNSUPPORTED_MONITORING]
    const wrapper = mountEditor(deployment(UNSUPPORTED_MONITORING.id))
    await flushPromises()

    expect(wrapper.find('[data-testid="editor-monitoring-toggle"]').exists()).toBe(false)
  })

  it('keeps monitoring visible so a saved deployment can turn it off after capability loss', async () => {
    satellitesStore.satellitesList = [UNSUPPORTED_MONITORING]
    const wrapper = mountEditor(deployment(UNSUPPORTED_MONITORING.id, MonitoringMode.full))
    await flushPromises()

    expect(wrapper.find('[data-testid="editor-monitoring-toggle"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('does not report the monitoring capability')
  })

  it('shows a read-only provider handle when the deployment has one', async () => {
    const wrapper = mountEditor({
      ...deployment(MONITORED.id),
      provider_ref: 'deployment/provider-job-123',
    })
    await flushPromises()

    const providerReference = wrapper.get('[data-testid="deployment-provider-reference"]')
    expect(providerReference.text()).toContain('Provider handle')
    expect(providerReference.text()).toContain('deployment/provider-job-123')
  })

  it('keeps the old editor unchanged when no provider handle is present', async () => {
    const wrapper = mountEditor()
    await flushPromises()

    expect(wrapper.find('[data-testid="deployment-provider-reference"]').exists()).toBe(false)
  })
})

describe('deployment form submission with both dialogs open', () => {
  const cleanup: (() => void)[] = []

  beforeEach(() => {
    deploymentsStore.createDeployment.mockReset()
    deploymentsStore.createDeployment.mockResolvedValue(undefined)
    deploymentsStore.update.mockReset()
    deploymentsStore.update.mockResolvedValue(undefined)
    artifactsStore.getArtifact.mockResolvedValue(modelWithTags([]))
  })

  afterEach(() => {
    cleanup.splice(0).forEach((unmount) => unmount())
    document.body.replaceChildren()
  })

  async function mountDialogs(editorFirst: boolean) {
    const editorTemplate = '<DeploymentsEditor :data="deployment" :visible="true" />'
    const modalTemplate = '<DeploymentsCreateModal :visible="true" />'
    const wrapper = mount(
      {
        components: { DeploymentsEditor, DeploymentsCreateModal },
        data: () => ({ deployment: deployment(MONITORED.id) }),
        template: editorFirst ? editorTemplate + modalTemplate : modalTemplate + editorTemplate,
      },
      { attachTo: document.body, global: { stubs: formStubs } },
    )
    cleanup.push(() => wrapper.unmount())
    const openEditor = wrapper.getComponent(DeploymentsEditor)
    const modal = wrapper.getComponent(DeploymentsCreateModal)

    modal
      .getComponent({ name: 'DeploymentsFormBasicsSettings' })
      .vm.$emit('update:name', 'new-deployment')
    const modelSettings = modal.getComponent({ name: 'DeploymentsFormModelSettings' })
    modelSettings.vm.$emit('update:modelId', 'new-model')
    await nextTick()
    modelSettings.vm.$emit('model-changed', { id: 'new-model' })
    modal
      .getComponent({ name: 'DeploymentsFormSatelliteSettings' })
      .vm.$emit('update:satelliteId', MONITORED.id)
    await flushPromises()

    return { editor: openEditor, modal }
  }

  it.each([true, false])(
    'Deploy creates a deployment and leaves the editor untouched (editor first: %s)',
    async (editorFirst) => {
      const { editor, modal } = await mountDialogs(editorFirst)

      ;(modal.get('button[type="submit"]').element as HTMLButtonElement).click()
      await flushPromises()

      expect(deploymentsStore.createDeployment).toHaveBeenCalledExactlyOnceWith(
        'org-1',
        'orbit-1',
        expect.objectContaining({ name: 'new-deployment', artifact_id: 'new-model' }),
      )
      expect(deploymentsStore.update).not.toHaveBeenCalled()
      expect(editor.emitted('update:visible')).toBeUndefined()
      expect(editor.getComponent({ name: 'DeploymentsFormBasicsSettings' }).props('name')).toBe(
        'Deployment',
      )
      expect(modal.emitted('update:visible')).toEqual([[false]])
    },
  )

  it.each([true, false])(
    'Save changes updates only the editor deployment (editor first: %s)',
    async (editorFirst) => {
      const { editor, modal } = await mountDialogs(editorFirst)
      editor
        .getComponent({ name: 'DeploymentsFormBasicsSettings' })
        .vm.$emit('update:name', 'Renamed deployment')
      await nextTick()
      ;(editor.get('button[type="submit"]').element as HTMLButtonElement).click()
      await flushPromises()

      expect(deploymentsStore.update).toHaveBeenCalledExactlyOnceWith(
        'org-1',
        'orbit-1',
        'deployment-1',
        { name: 'Renamed deployment' },
      )
      expect(deploymentsStore.createDeployment).not.toHaveBeenCalled()
      expect(modal.emitted('update:visible')).toBeUndefined()
      expect(editor.emitted('update:visible')).toEqual([[false]])
    },
  )
})

describe('DeploymentsEditor validation', () => {
  beforeEach(() => {
    deploymentsStore.update.mockReset()
    artifactsStore.getArtifact.mockResolvedValue(modelWithTags([]))
  })

  it('does not update a deployment when the form is invalid', async () => {
    const wrapper = mountEditor()
    await flushPromises()
    const form = wrapper.findComponent({ name: 'Form' })

    expect(form.props('resolver')).toBe(deploymentEditorResolver)
    form.vm.$emit('submit', { valid: false })
    await flushPromises()

    expect(deploymentsStore.update).not.toHaveBeenCalled()
  })

  it('accepts a deployment without a description', async () => {
    const result = await deploymentEditorResolver({
      values: { name: 'prod-deployment', description: null, tags: [] },
    } as never)

    expect(result.errors).toEqual({})
  })

  it.each(['', '   '])('rejects the blank name %j', async (name) => {
    const result = await deploymentEditorResolver({
      values: { name, description: null, tags: [] },
    } as never)

    expect(Object.keys(result.errors)).toEqual(['name'])
  })
})

describe('DeploymentsEditor saves', () => {
  beforeEach(() => {
    satellitesStore.satellitesList = [MONITORED]
    satellitesStore.loadSatellites.mockReset().mockResolvedValue([MONITORED])
    satellitesStore.setList.mockImplementation((satellites) => {
      satellitesStore.satellitesList = satellites
    })
    secretsStore.loadSecrets.mockReset().mockResolvedValue(undefined)
    artifactsStore.getArtifact.mockReset().mockResolvedValue(modelWithTags([]))
    dynamicAttributes.getDynamicAttributes.mockReturnValue({
      secrets: [{ name: 'token' }, { name: 'password' }],
    })
    deploymentsStore.update.mockReset().mockResolvedValue(undefined)
  })

  function savedDeployment() {
    return {
      ...deployment(MONITORED.id),
      tags: ['production'],
      dynamic_attributes_secrets: { token: 'secret-1', password: 'secret-2' },
    }
  }

  function saveButton(wrapper: ReturnType<typeof mountEditor>) {
    return wrapper.get('button[type="submit"]')
  }

  async function submit(wrapper: ReturnType<typeof mountEditor>) {
    wrapper.findComponent({ name: 'Form' }).vm.$emit('submit', { valid: true })
    await flushPromises()
  }

  it.each(['satellites', 'secrets', 'artifact'] as const)(
    'disables Save and ignores submission until %s initialization finishes',
    async (stage) => {
      let finish!: () => void
      const pending = new Promise<void>((resolve) => {
        finish = resolve
      })
      if (stage === 'satellites') {
        satellitesStore.satellitesList = []
        satellitesStore.loadSatellites.mockImplementationOnce(async () => {
          await pending
          return [MONITORED]
        })
      } else if (stage === 'secrets') {
        secretsStore.loadSecrets.mockImplementationOnce(() => pending)
      } else {
        artifactsStore.getArtifact.mockImplementationOnce(async () => {
          await pending
          return modelWithTags([])
        })
      }
      const wrapper = mountEditor(savedDeployment())
      await flushPromises()
      expect(saveButton(wrapper).attributes('disabled')).toBeDefined()
      await submit(wrapper)
      expect(deploymentsStore.update).not.toHaveBeenCalled()

      finish()
      await flushPromises()
      expect(saveButton(wrapper).attributes('disabled')).toBeUndefined()
      await submit(wrapper)
      expect(deploymentsStore.update).toHaveBeenCalledWith('org-1', 'orbit-1', 'deployment-1', {})
    },
  )

  it.each(['satellites', 'secrets', 'artifact', 'missing artifact'] as const)(
    'keeps Save disabled after %s initialization fails',
    async (stage) => {
      if (stage === 'satellites') {
        satellitesStore.satellitesList = []
        satellitesStore.loadSatellites.mockRejectedValueOnce(new Error('load failed'))
      } else if (stage === 'secrets') {
        secretsStore.loadSecrets.mockRejectedValueOnce(new Error('load failed'))
      } else if (stage === 'artifact') {
        artifactsStore.getArtifact.mockRejectedValueOnce(new Error('load failed'))
      } else {
        artifactsStore.getArtifact.mockResolvedValueOnce(null)
      }
      const wrapper = mountEditor(savedDeployment())
      await flushPromises()
      expect(saveButton(wrapper).attributes('disabled')).toBeDefined()
      await submit(wrapper)
      expect(deploymentsStore.update).not.toHaveBeenCalled()
      expect(wrapper.emitted('update:visible')).toBeUndefined()
    },
  )

  it('sends only a changed name and leaves saved secret bindings untouched', async () => {
    const wrapper = mountEditor(savedDeployment())
    await flushPromises()
    wrapper
      .findComponent({ name: 'DeploymentsFormBasicsSettings' })
      .vm.$emit('update:name', 'Renamed')
    await submit(wrapper)
    expect(deploymentsStore.update).toHaveBeenCalledWith('org-1', 'orbit-1', 'deployment-1', {
      name: 'Renamed',
    })
  })

  it('initializes null tags and omits them from an unchanged save', async () => {
    const data = { ...savedDeployment(), tags: null } as unknown as Deployment
    const wrapper = mountEditor(data)
    await flushPromises()

    expect(saveButton(wrapper).attributes('disabled')).toBeUndefined()
    expect(wrapper.findComponent({ name: 'DeploymentsFormBasicsSettings' }).props('tags')).toEqual(
      [],
    )
    await submit(wrapper)
    expect(deploymentsStore.update).toHaveBeenCalledWith('org-1', 'orbit-1', 'deployment-1', {})
    expect(data.tags).toBeNull()
  })

  it('preserves null tags when saving another field', async () => {
    const data = { ...savedDeployment(), tags: null } as unknown as Deployment
    const wrapper = mountEditor(data)
    await flushPromises()
    wrapper
      .findComponent({ name: 'DeploymentsFormBasicsSettings' })
      .vm.$emit('update:name', 'Renamed')
    await submit(wrapper)

    expect(deploymentsStore.update).toHaveBeenCalledWith('org-1', 'orbit-1', 'deployment-1', {
      name: 'Renamed',
    })
    expect(data.tags).toBeNull()
  })

  it('sends tags added to a deployment with null tags', async () => {
    const data = { ...savedDeployment(), tags: null } as unknown as Deployment
    const wrapper = mountEditor(data)
    await flushPromises()
    const basics = wrapper.findComponent({ name: 'DeploymentsFormBasicsSettings' })
    basics.vm.$emit('update:tags', ['production'])
    await submit(wrapper)

    expect(deploymentsStore.update).toHaveBeenLastCalledWith('org-1', 'orbit-1', 'deployment-1', {
      tags: ['production'],
    })
    expect(data.tags).toBeNull()
  })

  it('omits tags reverted to empty when the saved tags are null', async () => {
    const data = { ...savedDeployment(), tags: null } as unknown as Deployment
    const wrapper = mountEditor(data)
    await flushPromises()
    const basics = wrapper.findComponent({ name: 'DeploymentsFormBasicsSettings' })
    basics.vm.$emit('update:tags', ['production'])
    basics.vm.$emit('update:tags', [])
    await submit(wrapper)
    expect(deploymentsStore.update).toHaveBeenLastCalledWith('org-1', 'orbit-1', 'deployment-1', {})
    expect(data.tags).toBeNull()
  })

  it('sends changed description, tags, and monitoring without untouched fields', async () => {
    const data = savedDeployment()
    const wrapper = mountEditor(data)
    await flushPromises()
    const basics = wrapper.findComponent({ name: 'DeploymentsFormBasicsSettings' })
    basics.vm.$emit('update:description', 'New description')
    basics.vm.$emit('update:tags', ['production', 'updated'])
    wrapper.findComponent({ name: 'ToggleSwitch' }).vm.$emit('update:modelValue', true)
    await submit(wrapper)
    expect(deploymentsStore.update).toHaveBeenCalledWith('org-1', 'orbit-1', 'deployment-1', {
      description: 'New description',
      tags: ['production', 'updated'],
      monitoring_mode: MonitoringMode.full,
    })
    expect(data.tags).toEqual(['production'])
  })

  it('preserves untouched and undisplayed bindings when changing a secret', async () => {
    const data = {
      ...savedDeployment(),
      dynamic_attributes_secrets: {
        ...savedDeployment().dynamic_attributes_secrets,
        legacy: 'secret-3',
      },
    }
    const wrapper = mountEditor(data)
    await flushPromises()
    wrapper
      .findAllComponents({ name: 'SecretsSelect' })[0]
      .vm.$emit('update:modelValue', 'secret-4')
    await submit(wrapper)
    expect(deploymentsStore.update).toHaveBeenCalledWith('org-1', 'orbit-1', 'deployment-1', {
      dynamic_attributes_secrets: { token: 'secret-4', password: 'secret-2', legacy: 'secret-3' },
    })
    expect(data.dynamic_attributes_secrets.token).toBe('secret-1')
  })

  it('sends an empty binding map when the user explicitly clears every secret', async () => {
    const wrapper = mountEditor(savedDeployment())
    await flushPromises()
    for (const select of wrapper.findAllComponents({ name: 'SecretsSelect' })) {
      select.vm.$emit('update:modelValue', null)
    }
    await submit(wrapper)
    expect(deploymentsStore.update).toHaveBeenCalledWith('org-1', 'orbit-1', 'deployment-1', {
      dynamic_attributes_secrets: {},
    })
  })

  it('omits fields changed back to their saved values', async () => {
    const wrapper = mountEditor(savedDeployment())
    await flushPromises()
    const basics = wrapper.findComponent({ name: 'DeploymentsFormBasicsSettings' })
    const secret = wrapper.findAllComponents({ name: 'SecretsSelect' })[0]
    basics.vm.$emit('update:name', 'Renamed')
    basics.vm.$emit('update:name', 'Deployment')
    basics.vm.$emit('update:tags', ['production'])
    secret.vm.$emit('update:modelValue', 'secret-4')
    secret.vm.$emit('update:modelValue', 'secret-1')
    await submit(wrapper)
    expect(deploymentsStore.update).toHaveBeenCalledWith('org-1', 'orbit-1', 'deployment-1', {})
  })

  it('does not send an empty secret map for a deployment without secret fields', async () => {
    dynamicAttributes.getDynamicAttributes.mockReturnValue({ secrets: [] })
    const wrapper = mountEditor()
    await flushPromises()
    await submit(wrapper)
    expect(deploymentsStore.update).toHaveBeenCalledWith('org-1', 'orbit-1', 'deployment-1', {})
  })

  it('blocks duplicate submissions while saving and allows retry after update failure', async () => {
    let fail!: (error: Error) => void
    deploymentsStore.update.mockImplementationOnce(
      () =>
        new Promise((_, reject) => {
          fail = reject
        }),
    )
    const wrapper = mountEditor(savedDeployment())
    await flushPromises()
    wrapper
      .findComponent({ name: 'DeploymentsFormBasicsSettings' })
      .vm.$emit('update:name', 'Renamed')
    await submit(wrapper)
    expect(saveButton(wrapper).attributes('disabled')).toBeDefined()
    await submit(wrapper)
    expect(deploymentsStore.update).toHaveBeenCalledTimes(1)

    fail(new Error('update failed'))
    await flushPromises()
    expect(saveButton(wrapper).attributes('disabled')).toBeUndefined()
    expect(wrapper.emitted('update:visible')).toBeUndefined()
    await submit(wrapper)
    expect(deploymentsStore.update).toHaveBeenLastCalledWith('org-1', 'orbit-1', 'deployment-1', {
      name: 'Renamed',
    })
    expect(wrapper.emitted('update:visible')).toEqual([[false]])
  })
})
