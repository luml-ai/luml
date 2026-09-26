import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import {
  DeploymentStatusEnum,
  MonitoringMode,
  type Deployment,
} from '@/lib/api/deployments/interfaces'
import DeploymentsTable from './DeploymentsTable.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {}, params: {} }),
  useRouter: () => ({ replace: vi.fn() }),
}))

vi.mock('primevue', async () => {
  const { computed, defineComponent, h, inject, provide } = await import('vue')
  const tableRows = Symbol('tableRows')
  const passthrough = (name: string) =>
    defineComponent({
      name,
      setup:
        (_, { slots }) =>
        () =>
          h('div', slots.default?.()),
    })

  const DataTable = defineComponent({
    name: 'DataTable',
    props: { value: { type: Array, default: () => [] } },
    setup: (props, { slots }) => {
      provide(
        tableRows,
        computed(() => props.value),
      )
      return () => h('div', [slots.header?.(), slots.default?.()])
    },
  })
  const Column = defineComponent({
    name: 'ColumnStub',
    setup: (_, { slots }) => {
      const rows = inject<Readonly<{ value: unknown[] }>>(tableRows, { value: [] })
      return () =>
        h(
          'div',
          rows.value.flatMap((data) => slots.body?.({ data }) ?? []),
        )
    },
  })

  return {
    DataTable,
    Column,
    IconField: passthrough('IconField'),
    InputIcon: passthrough('InputIcon'),
    InputText: defineComponent({
      name: 'InputText',
      inheritAttrs: false,
      setup: () => () => h('input'),
    }),
    Tag: defineComponent({
      name: 'TagStub',
      setup:
        (_, { slots }) =>
        () =>
          h('span', slots.default?.()),
    }),
    Button: defineComponent({
      name: 'ButtonStub',
      setup:
        (_, { slots }) =>
        () =>
          h('button', slots.default?.()),
    }),
  }
})

function deployment(status: DeploymentStatusEnum, progressNote?: string): Deployment {
  return {
    id: `${status}-${progressNote ?? 'old'}`,
    orbit_id: 'orbit-1',
    satellite_id: 'satellite-1',
    artifact_id: 'artifact-1',
    inference_url: '/deployments/deployment-1',
    status,
    monitoring_mode: MonitoringMode.off,
    secrets: {},
    created_by_user: 'user@example.com',
    tags: [],
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    satellite_name: 'Satellite',
    name: 'Deployment',
    description: '',
    collection_id: 'collection-1',
    dynamic_attributes_secrets: {},
    artifact_name: 'Model',
    error_message: null,
    schemas: {},
    progress_note: progressNote,
  }
}

function mountTable(data: Deployment[]) {
  return mount(DeploymentsTable, {
    props: { data },
    global: {
      directives: { tooltip: () => undefined },
      stubs: {
        RouterLink: { template: '<a><slot /></a>' },
        DeploymentsEditor: true,
        DeploymentErrorModal: true,
        UiId: { props: ['id'], template: '<span>{{ id }}</span>' },
      },
    },
  })
}

describe('DeploymentsTable progress notes', () => {
  it('shows notes below pending and not-responding statuses only', () => {
    const wrapper = mountTable([
      deployment(DeploymentStatusEnum.pending, '0/3 pods ready'),
      deployment(DeploymentStatusEnum.not_responding, 'Recovering workload'),
      deployment(DeploymentStatusEnum.active, 'This note is stale'),
    ])

    expect(
      wrapper.findAll('[data-testid="deployment-progress-note"]').map((note) => note.text()),
    ).toEqual(['0/3 pods ready', 'Recovering workload'])
  })

  it('adds no status detail for an old deployment without a note', () => {
    const wrapper = mountTable([deployment(DeploymentStatusEnum.pending)])

    expect(wrapper.find('[data-testid="deployment-progress-note"]').exists()).toBe(false)
  })
})

describe('DeploymentsTable count label', () => {
  it.each([
    [0, '0 Deployments'],
    [1, '1 Deployment'],
    [2, '2 Deployments'],
  ])('renders %s deployments as %s', (count, label) => {
    const data = Array.from({ length: count }, (_, index) =>
      deployment(DeploymentStatusEnum.active, String(index)),
    )

    expect(mountTable(data).get('.title').text()).toBe(label)
  })
})
