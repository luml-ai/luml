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
  loadSecrets: vi.fn(async () => undefined),
}

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
  FnnxService: { getDynamicAttributes: () => ({ secrets: [] }) },
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
    global: { stubs: formStubs },
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

      ;(editor.get('button[type="submit"]').element as HTMLButtonElement).click()
      await flushPromises()

      expect(deploymentsStore.update).toHaveBeenCalledExactlyOnceWith(
        'org-1',
        'orbit-1',
        'deployment-1',
        expect.objectContaining({ name: 'Deployment' }),
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
