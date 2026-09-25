import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import {
  MonitoringFeature,
  SatelliteFieldTypeEnum,
  type SatelliteField,
} from '@/lib/api/satellites/interfaces'
import kubernetesFields from '../../../../../satellite/implementations/kubernetes/tests/snapshots/settings_fields.json'
import type { SatelliteFieldInfo } from '../deployments.interfaces'
import DeploymentsFormSatelliteSettings from './DeploymentsFormSatelliteSettings.vue'

enableAutoUnmount(afterEach)

const TABULAR_KIND_TAG = 'luml.ai::kind_tabular:v1'
const LLM_KIND_TAG = 'luml.ai::kind_llm:v1'
const TABULAR_MONITORING_TAG = 'luml.ai::tabular_monitoring:v1'

const DEPLOY_CAPABILITY = {
  version: 1,
  api_versions: [1],
  facets: ['satellite', 'deployment'],
  supported_variants: ['pyfunc'],
  supported_tags_combinations: null,
  extra_fields_form_spec: [],
}

const ALL_MONITORING_FEATURES = Object.values(MonitoringFeature)

const KUBERNETES_FIELDS = kubernetesFields as SatelliteField[]

function monitoringCapability(features = ALL_MONITORING_FEATURES) {
  return {
    version: 1,
    api_versions: [1],
    facets: ['deployment:monitoring'],
    features,
  }
}

const MONITORED = {
  id: 'sat-monitored',
  name: 'Monitored satellite',
  present_capabilities: ['deploy', 'monitoring'],
  capabilities: {
    deploy: DEPLOY_CAPABILITY,
    monitoring: monitoringCapability(),
  },
}

const PLAIN = {
  id: 'sat-plain',
  name: 'Plain satellite',
  present_capabilities: ['deploy'],
  capabilities: {
    deploy: DEPLOY_CAPABILITY,
    monitoring: { ...monitoringCapability(), api_versions: [9] },
  },
}

const RAW_DEPLOY_ONLY = {
  id: 'sat-raw-deploy',
  name: 'Unsupported deploy satellite',
  present_capabilities: ['monitoring'],
  capabilities: {
    deploy: { ...DEPLOY_CAPABILITY, api_versions: [9] },
    monitoring: monitoringCapability(),
  },
}

const REDUCED_MONITORING = {
  id: 'sat-reduced',
  name: 'Reduced monitoring satellite',
  present_capabilities: ['deploy', 'monitoring'],
  capabilities: {
    deploy: DEPLOY_CAPABILITY,
    monitoring: monitoringCapability(
      ALL_MONITORING_FEATURES.filter((feature) => feature !== MonitoringFeature.output_drift),
    ),
  },
}

const KUBERNETES = {
  id: 'sat-kubernetes',
  name: 'Kubernetes satellite',
  present_capabilities: ['deploy'],
  capabilities: {
    deploy: { ...DEPLOY_CAPABILITY, extra_fields_form_spec: KUBERNETES_FIELDS },
  },
}

const OLD_DECLARATION = {
  id: 'sat-old',
  name: 'Old satellite',
  present_capabilities: ['deploy'],
  capabilities: {
    deploy: {
      ...DEPLOY_CAPABILITY,
      extra_fields_form_spec: [
        {
          name: 'legacy_setting',
          type: SatelliteFieldTypeEnum.text,
          values: null,
          required: false,
          validators: [],
          conditions: [],
        },
      ],
    },
  },
}

const satellitesStore = reactive({
  satellitesList: [MONITORED, PLAIN, RAW_DEPLOY_ONLY] as unknown[],
  loadSatellites: vi.fn(async () => [MONITORED, PLAIN, RAW_DEPLOY_ONLY]),
  setList: vi.fn(),
})

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { organizationId: 'org-1', id: 'orbit-1' } }),
}))

vi.mock('@/stores/satellites', () => ({
  useSatellitesStore: () => satellitesStore,
}))

vi.mock('primevue', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>
  return { ...actual, useToast: () => ({ add: vi.fn() }) }
})

const SELECTED_MODEL = modelWithTags([])

function modelWithTags(producerTags: string[]) {
  return {
    manifest: { variant: 'pyfunc', producer_tags: producerTags },
  } as never
}

function mountForm(props: Record<string, unknown> = {}) {
  return mount(DeploymentsFormSatelliteSettings, {
    props: {
      selectedModel: SELECTED_MODEL,
      satelliteId: null,
      fields: [],
      monitoringEnabled: false,
      ...props,
    },
    global: {
      stubs: {
        Select: {
          name: 'Select',
          props: ['options'],
          template: `
            <div data-testid="satellite-select">
              <template v-for="group in options" :key="group.label">
                <span v-for="option in group.items" :key="option.id" class="satellite-option">
                  {{ option.name }}
                </span>
              </template>
            </div>
          `,
        },
        FormField: { template: '<div><slot /></div>' },
        InputText: {
          props: ['modelValue', 'size', 'required', 'placeholder'],
          template: '<input />',
        },
        InputNumber: {
          props: ['modelValue', 'size', 'required', 'placeholder'],
          template: '<input />',
        },
        ToggleButton: { props: ['modelValue', 'size'], template: '<button />' },
        ToggleSwitch: {
          template:
            '<button data-testid="toggle" @click="$emit(\'update:modelValue\', !modelValue)" />',
          props: ['modelValue'],
        },
      },
    },
  })
}

function monitoringSections(wrapper: ReturnType<typeof mountForm>): string {
  return wrapper.get('[data-testid="monitoring-sections-hint"]').text()
}

describe('DeploymentsFormSatelliteSettings', () => {
  beforeEach(() => {
    satellitesStore.satellitesList = [MONITORED, PLAIN, RAW_DEPLOY_ONLY]
  })

  it('offers only satellites with a present deploy capability', () => {
    const wrapper = mountForm()
    const options = wrapper.findAll('.satellite-option').map((option) => option.text())

    expect(options).toEqual([MONITORED.name, PLAIN.name])
    expect(options).not.toContain(RAW_DEPLOY_ONLY.name)
  })

  it('hides the monitoring block until a satellite is picked', () => {
    const wrapper = mountForm()

    expect(wrapper.find('[data-testid="create-monitoring-toggle"]').exists()).toBe(false)
  })

  it('offers the toggle when monitoring is present', () => {
    const wrapper = mountForm({ satelliteId: MONITORED.id })

    expect(wrapper.find('[data-testid="create-monitoring-toggle"]').exists()).toBe(true)
  })

  it('does not trust a raw monitoring declaration that is not present', () => {
    const wrapper = mountForm({ satelliteId: PLAIN.id })

    expect(wrapper.find('[data-testid="create-monitoring-toggle"]').exists()).toBe(false)
  })

  it('emits the new value so the create payload can carry monitoring_mode', async () => {
    const wrapper = mountForm({ satelliteId: MONITORED.id })

    await wrapper.find('[data-testid="create-monitoring-toggle"]').trigger('click')

    expect(wrapper.emitted('update:monitoringEnabled')).toEqual([[true]])
  })

  it('switching to a non-monitoring satellite drops the enabled value', async () => {
    const wrapper = mountForm({ satelliteId: MONITORED.id, monitoringEnabled: true })

    await wrapper.setProps({ satelliteId: PLAIN.id })

    expect(wrapper.emitted('update:monitoringEnabled')?.at(-1)).toEqual([false])
  })

  it('keeps an enabled field visible when the capability was lost and shows a warning', () => {
    const wrapper = mountForm({ monitoringEnabled: true, satelliteId: PLAIN.id })

    expect(wrapper.find('[data-testid="create-monitoring-toggle"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('does not report the monitoring capability')
  })

  it('lists every advertised section for a tagged tabular profile', () => {
    const wrapper = mountForm({
      satelliteId: MONITORED.id,
      selectedModel: modelWithTags([TABULAR_KIND_TAG, TABULAR_MONITORING_TAG]),
    })

    expect(monitoringSections(wrapper)).toContain('Runtime')
    expect(monitoringSections(wrapper)).toContain('Traces')
    expect(monitoringSections(wrapper)).toContain('Alerts')
    expect(monitoringSections(wrapper)).toContain('Data quality')
    expect(monitoringSections(wrapper)).toContain('Feature drift')
    expect(monitoringSections(wrapper)).toContain('Output drift')
    expect(monitoringSections(wrapper)).toContain('Multivariate drift')
    expect(wrapper.find('[data-testid="monitoring-repack-hint"]').exists()).toBe(false)
  })

  it('lists universal sections and recommends repacking for a tabular model without a profile tag', () => {
    const wrapper = mountForm({
      satelliteId: MONITORED.id,
      selectedModel: modelWithTags([TABULAR_KIND_TAG]),
    })

    expect(monitoringSections(wrapper)).toContain('Runtime, Traces, Alerts')
    expect(monitoringSections(wrapper)).not.toContain('drift')
    expect(wrapper.get('[data-testid="monitoring-repack-hint"]').text()).toContain(
      'Repack this model with reference data',
    )
  })

  it.each([
    ['an LLM model', [LLM_KIND_TAG]],
    ['an untagged model', []],
  ])('lists only universal sections without a repack recommendation for %s', (_, tags) => {
    const wrapper = mountForm({
      satelliteId: MONITORED.id,
      selectedModel: modelWithTags(tags),
    })

    expect(monitoringSections(wrapper)).toContain('Runtime, Traces, Alerts')
    expect(monitoringSections(wrapper)).not.toContain('drift')
    expect(wrapper.find('[data-testid="monitoring-repack-hint"]').exists()).toBe(false)
  })

  it('omits a profile-dependent section the satellite does not advertise', () => {
    satellitesStore.satellitesList = [REDUCED_MONITORING]
    const wrapper = mountForm({
      satelliteId: REDUCED_MONITORING.id,
      selectedModel: modelWithTags([TABULAR_KIND_TAG, TABULAR_MONITORING_TAG]),
    })

    expect(monitoringSections(wrapper)).toContain('Data quality')
    expect(monitoringSections(wrapper)).toContain('Feature drift')
    expect(monitoringSections(wrapper)).toContain('Multivariate drift')
    expect(monitoringSections(wrapper)).not.toContain('Output drift')
  })

  it('seeds Kubernetes fields from defaults and reveals GPU fields only when enabled', async () => {
    satellitesStore.satellitesList = [KUBERNETES]
    const wrapper = mountForm()

    await wrapper.setProps({ satelliteId: KUBERNETES.id })
    await flushPromises()

    const defaultFields = wrapper.emitted('update:fields')?.at(-1)?.[0] as SatelliteFieldInfo[]
    expect(Object.fromEntries(defaultFields.map(({ key, value }) => [key, value]))).toEqual({
      replicas: 1,
      cpu_millicores: 1_000,
      memory: '2Gi',
      use_gpu: false,
      health_check_timeout: 1_800,
      log_level: 'info',
    })
    expect(defaultFields.some(({ key }) => key === 'gpu_count')).toBe(false)
    expect(defaultFields.some(({ key }) => key === 'gpu_resource_name')).toBe(false)

    await wrapper.setProps({
      fields: defaultFields.map((field) =>
        field.key === 'use_gpu' ? { ...field, value: true } : field,
      ),
    })
    await flushPromises()

    const gpuFields = wrapper.emitted('update:fields')?.at(-1)?.[0] as SatelliteFieldInfo[]
    expect(Object.fromEntries(gpuFields.map(({ key, value }) => [key, value]))).toMatchObject({
      use_gpu: true,
      gpu_count: 1,
      gpu_resource_name: 'nvidia.com/gpu',
    })
  })

  it('leaves fields empty when an old declaration has no defaults', async () => {
    satellitesStore.satellitesList = [OLD_DECLARATION]
    const wrapper = mountForm()

    await wrapper.setProps({ satelliteId: OLD_DECLARATION.id })
    await flushPromises()

    const fields = wrapper.emitted('update:fields')?.at(-1)?.[0] as SatelliteFieldInfo[]
    expect(fields).toHaveLength(1)
    expect(fields[0]).toMatchObject({ key: 'legacy_setting', value: null })
  })
})
