import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import { DeploymentStatusEnum, MonitoringMode } from '@/lib/api/deployments/interfaces'
import { MonitoringFeature } from '@/lib/api/satellites/interfaces'
import { deploymentEditorResolver } from '@/utils/forms/resolvers'
import DeploymentsEditor from './DeploymentsEditor.vue'

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

function deployment(satelliteId: string, monitoringMode = MonitoringMode.off) {
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
  } as never
}

function modelWithTags(producerTags: string[]) {
  return {
    manifest: { producer_tags: producerTags },
  }
}

function mountEditor(data = deployment(MONITORED.id)) {
  return mount(DeploymentsEditor, {
    props: { data, visible: true },
    global: {
      stubs: {
        Dialog: {
          props: ['visible'],
          template: '<div><slot name="header" /><slot /><slot name="footer" /></div>',
        },
        Form: {
          name: 'Form',
          props: ['resolver'],
          emits: ['submit'],
          template: '<form><slot /></form>',
        },
        FormField: { template: '<div><slot /></div>' },
        DeploymentsFormBasicsSettings: true,
        DeploymentsDelete: true,
        ForceDeleteConfirmDialog: true,
        SecretsSelect: true,
        Accordion: { template: '<div><slot /></div>' },
        AccordionPanel: { template: '<div><slot /></div>' },
        AccordionHeader: { template: '<div><slot /></div>' },
        AccordionContent: { template: '<div><slot /></div>' },
        ToggleSwitch: { template: '<button data-testid="editor-monitoring-toggle" />' },
        Button: { template: '<button><slot /></button>' },
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
