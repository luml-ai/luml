import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import {
  DeploymentStatusEnum,
  MonitoringMode,
  type Deployment,
} from '@/lib/api/deployments/interfaces'
import DeploymentsTable from './DeploymentsTable.vue'

const { batchAction } = vi.hoisted(() => ({ batchAction: vi.fn() }))
vi.mock('@/stores/deployments', () => ({ useDeploymentsStore: () => ({ batchAction }) }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {}, params: { organizationId: 'org-1', id: 'orbit-1' } }),
  useRouter: () => ({ replace: vi.fn() }),
}))

function deployment(index: number, status = DeploymentStatusEnum.active): Deployment {
  return {
    id: `deployment-${index}`,
    name: `Deployment ${index}`,
    orbit_id: 'orbit-1',
    satellite_id: 'satellite-1',
    artifact_id: 'artifact-1',
    collection_id: 'collection-1',
    satellite_name: 'Satellite',
    artifact_name: 'Model',
    inference_url: '',
    status,
    monitoring_mode: MonitoringMode.off,
    secrets: {},
    tags: [],
    created_by_user: 'User',
    created_at: '',
    updated_at: '',
    description: '',
    dynamic_attributes_secrets: {},
    schemas: {},
    error_message: null,
  }
}

function mountTable(data = [deployment(1), deployment(2)]) {
  return mount(DeploymentsTable, {
    props: { data },
    global: {
      plugins: [PrimeVue, ToastService],
      directives: { tooltip: () => undefined },
      stubs: {
        RouterLink: { template: '<a><slot /></a>' },
        DeploymentsEditor: true,
        DeploymentErrorModal: true,
        UiId: true,
        Dialog: {
          props: ['visible'],
          template:
            '<div v-if="visible"><slot name="header" /><slot /><slot name="footer" /></div>',
        },
        ForceDeleteConfirmDialog: {
          props: ['visible'],
          emits: ['confirm'],
          template:
            '<button v-if="visible" data-testid="force-confirm" @click="$emit(\'confirm\')">Confirm force delete</button>',
        },
      },
    },
  })
}

beforeEach(() => {
  batchAction.mockReset()
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
  )
})
afterEach(() => {
  vi.unstubAllGlobals()
})

describe('DeploymentsTable selection and batch actions', () => {
  it('selects individual rows, shows the count, and clears the action bar', async () => {
    const wrapper = mountTable()
    expect(wrapper.find('[data-testid="deployment-actions"]').exists()).toBe(false)
    await wrapper.findAll('input[type="checkbox"]')[1].setValue(true)
    expect(wrapper.get('[data-testid="deployment-actions"]').text()).toContain('1 selected')
    await wrapper.findAll('input[type="checkbox"]')[2].setValue(true)
    expect(wrapper.get('[data-testid="deployment-actions"]').text()).toContain('2 selected')
    await wrapper.get('[data-testid="clear-selection"]').trigger('click')
    expect(wrapper.find('[data-testid="deployment-actions"]').exists()).toBe(false)
  })

  it('selects all across pages and keeps selected rows after a status refresh', async () => {
    const data = Array.from({ length: 12 }, (_, index) => deployment(index))
    const wrapper = mountTable(data)
    await wrapper.findAll('input[type="checkbox"]')[0].setValue(true)
    expect(wrapper.get('[data-testid="deployment-actions"]').text()).toContain('12 selected')
    await wrapper.get('[aria-label="Next Page"]').trigger('click')
    expect(
      wrapper
        .findAll('input[type="checkbox"]')
        .slice(1)
        .every((input) => (input.element as HTMLInputElement).checked),
    ).toBe(true)
    await wrapper.setProps({
      data: data.map((row) => ({ ...row, status: DeploymentStatusEnum.not_responding })),
    })
    expect(wrapper.get('[data-testid="deployment-actions"]').text()).toContain('12 selected')
    expect(
      wrapper
        .findAll('input[type="checkbox"]')
        .slice(1)
        .every((input) => (input.element as HTMLInputElement).checked),
    ).toBe(true)
    await wrapper.findAll('input[type="checkbox"]')[1].setValue(false)
    expect(wrapper.get('[data-testid="deployment-actions"]').text()).toContain('11 selected')
  }, 15000)

  it('submits the whole selection and reports success and refusal per deployment', async () => {
    batchAction.mockResolvedValue({
      succeeded: ['deployment-1'],
      failed: [
        {
          deployment_id: 'deployment-2',
          name: 'Deployment 2',
          reason: 'already_pending',
          message: 'Deployment deletion already pending',
        },
      ],
    })
    const wrapper = mountTable()
    await wrapper.findAll('input[type="checkbox"]')[0].setValue(true)
    await wrapper.get('[data-testid="batch-stop"]').trigger('click')
    expect(batchAction).not.toHaveBeenCalled()
    await wrapper.get('[data-testid="confirm-stop"]').trigger('click')
    await flushPromises()
    expect(batchAction).toHaveBeenCalledWith(
      'org-1',
      'orbit-1',
      ['deployment-1', 'deployment-2'],
      'undeploy',
    )
    const results = wrapper.get('[data-testid="batch-results"]').text()
    expect(results).toContain('Deployment 1')
    expect(results).toContain('Stop requested')
    expect(results).toContain('Deployment 2')
    expect(results).toContain('Deployment deletion already pending')
    expect(wrapper.get('[data-testid="deployment-actions"]').text()).toContain('1 selected')
  })

  it('requires confirmation for force deletion and submits every selected row', async () => {
    batchAction.mockResolvedValue({ succeeded: ['deployment-1', 'deployment-2'], failed: [] })
    const wrapper = mountTable([
      deployment(1, DeploymentStatusEnum.failed),
      deployment(2, DeploymentStatusEnum.not_responding),
    ])
    await wrapper.findAll('input[type="checkbox"]')[0].setValue(true)
    await wrapper.get('[data-testid="batch-delete"]').trigger('click')
    expect(batchAction).not.toHaveBeenCalled()
    await wrapper.get('[data-testid="force-confirm"]').trigger('click')
    await flushPromises()
    expect(batchAction).toHaveBeenCalledWith(
      'org-1',
      'orbit-1',
      ['deployment-1', 'deployment-2'],
      'delete',
    )
    expect(wrapper.get('[data-testid="batch-results"]').text()).toContain('Deleted')
    expect(wrapper.find('[data-testid="deployment-actions"]').exists()).toBe(false)
  })
})
