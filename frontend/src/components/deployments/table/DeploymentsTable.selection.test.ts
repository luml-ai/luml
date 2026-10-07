import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PrimeVue from 'primevue/config'
import {
  DeploymentStatusEnum,
  MonitoringMode,
  type Deployment,
} from '@/lib/api/deployments/interfaces'
import DeploymentsTable from './DeploymentsTable.vue'

const { batchAction, confirmRequire, toastAdd } = vi.hoisted(() => ({
  batchAction: vi.fn(),
  confirmRequire: vi.fn(),
  toastAdd: vi.fn(),
}))
vi.mock('@/stores/deployments', () => ({ useDeploymentsStore: () => ({ batchAction }) }))
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useConfirm: () => ({ require: confirmRequire }),
  useToast: () => ({ add: toastAdd }),
}))
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
      plugins: [PrimeVue],
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
  confirmRequire.mockReset()
  toastAdd.mockReset()
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
  )
})
afterEach(() => {
  vi.unstubAllGlobals()
})

function counter(wrapper: ReturnType<typeof mountTable>) {
  return wrapper.get('.counter').text()
}

describe('DeploymentsTable selection and batch actions', () => {
  it('selects individual rows and enables the toolbar actions only with a selection', async () => {
    const wrapper = mountTable()
    expect(counter(wrapper)).toBe('0 Selected')
    expect(wrapper.get('[data-testid="batch-stop"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="batch-delete"]').attributes('disabled')).toBeDefined()
    await wrapper.findAll('input[type="checkbox"]')[1].setValue(true)
    expect(counter(wrapper)).toBe('1 Selected')
    expect(wrapper.get('[data-testid="batch-stop"]').attributes('disabled')).toBeUndefined()
    await wrapper.findAll('input[type="checkbox"]')[2].setValue(true)
    expect(counter(wrapper)).toBe('2 Selected')
    await wrapper.findAll('input[type="checkbox"]')[1].setValue(false)
    expect(counter(wrapper)).toBe('1 Selected')
  })

  it('renders every row without pagination and keeps the selection after a status refresh', async () => {
    const data = Array.from({ length: 12 }, (_, index) => deployment(index))
    const wrapper = mountTable(data)
    expect(wrapper.find('.p-paginator').exists()).toBe(false)
    expect(wrapper.findAll('tbody tr')).toHaveLength(12)
    await wrapper.findAll('input[type="checkbox"]')[0].setValue(true)
    expect(counter(wrapper)).toBe('12 Selected')
    await wrapper.setProps({
      data: data.map((row) => ({ ...row, status: DeploymentStatusEnum.not_responding })),
    })
    expect(counter(wrapper)).toBe('12 Selected')
    expect(
      wrapper
        .findAll('input[type="checkbox"]')
        .slice(1)
        .every((input) => (input.element as HTMLInputElement).checked),
    ).toBe(true)
  }, 15000)

  it('stops the selection after confirmation and reports refusals', async () => {
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
    expect(confirmRequire).toHaveBeenCalledWith(
      expect.objectContaining({ header: 'Stop 2 deployments?' }),
    )
    confirmRequire.mock.calls[0][0].accept()
    await flushPromises()
    expect(batchAction).toHaveBeenCalledWith(
      'org-1',
      'orbit-1',
      ['deployment-1', 'deployment-2'],
      'undeploy',
    )
    expect(toastAdd).toHaveBeenCalledWith(
      expect.objectContaining({
        severity: 'success',
        detail: 'Deployment "Deployment 1" is stopping',
      }),
    )
    const results = wrapper.get('[data-testid="batch-results"]').text()
    expect(results).toContain('Deployment 2')
    expect(results).toContain('Deployment deletion already pending')
    expect(results).not.toContain('Deployment 1')
    expect(counter(wrapper)).toBe('1 Selected')
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
    expect(toastAdd).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'success', detail: '2 deployments deleted' }),
    )
    expect(wrapper.find('[data-testid="batch-results"]').exists()).toBe(false)
    expect(counter(wrapper)).toBe('0 Selected')
  })
})
