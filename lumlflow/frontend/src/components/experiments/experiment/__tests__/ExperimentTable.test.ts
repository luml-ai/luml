// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { nextTick, reactive } from 'vue'
import type { GetExperimentsParams, PaginatedResponse } from '@/api/api.interface'
import type { Experiment } from '@/store/experiments/experiments.interface'
import { usePagination } from '@/hooks/usePagination'
import { useExperimentsStore } from '@/store/experiments'
import ExperimentTable from '../ExperimentTable.vue'

vi.mock('@/store/experiments', () => ({ useExperimentsStore: vi.fn() }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('../ExperimentModelsListColumn.vue', () => ({ default: { template: '<span />' } }))

describe('ExperimentTable loading', () => {
  beforeEach(() => vi.clearAllMocks())

  const mountingOptions = {
    props: { groupsIds: [], dynamicMetrics: [] },
    global: {
      directives: { tooltip: {} },
      stubs: {
        DataTable: {
          name: 'DataTable',
          props: ['loading', 'pt'],
          inheritAttrs: false,
          template: '<div />',
        },
      },
    },
  }

  it('clears the table spinner and shows the empty state after an initial request fails', async () => {
    let reject!: (error: Error) => void
    const page = new Promise<PaginatedResponse<Experiment>>((_, rej) => {
      reject = rej
    })
    const pagination = usePagination<Experiment, GetExperimentsParams>(() => page)
    const store = reactive({
      experiments: pagination.data,
      isLoading: pagination.isLoading,
      selectedExperiments: [],
      visibleColumns: [],
      queryParams: {},
      setTableColumns: vi.fn(),
      setVisibleColumns: vi.fn(),
      setQueryParams: vi.fn(),
      reset: pagination.reset,
      onLazyLoad: pagination.onLazyLoad,
    })
    vi.mocked(useExperimentsStore).mockReturnValue(
      store as unknown as ReturnType<typeof useExperimentsStore>,
    )
    const request = pagination.getInitialPage()
    const wrapper = shallowMount(ExperimentTable, mountingOptions)
    const table = wrapper.findComponent({ name: 'DataTable' })
    expect(table.props('loading')).toBe(true)
    expect(table.props('pt').emptyMessage).toBe('hidden')

    const error = new Error('request failed')
    const assertion = expect(request).rejects.toBe(error)
    reject(error)
    await assertion
    await nextTick()

    expect(table.props('loading')).toBe(false)
    expect(table.props('pt').emptyMessage).toBe('')
    wrapper.unmount()
  })

  it('keeps the table visible without a spinner while the next page is loading', async () => {
    let resolve!: (page: PaginatedResponse<Experiment>) => void
    const nextPage = new Promise<PaginatedResponse<Experiment>>((res) => {
      resolve = res
    })
    const experiment: Experiment = {
      id: 'experiment',
      name: 'first',
      created_at: '2026-10-07',
      tags: null,
      models: null,
      duration: 1,
      description: '',
      static_params: null,
      dynamic_params: null,
      status: 'completed',
      source: null,
      group_name: null,
      group_id: null,
    }
    const method = vi
      .fn()
      .mockResolvedValueOnce({ items: [experiment], cursor: 'next' })
      .mockReturnValueOnce(nextPage)
    const pagination = usePagination<Experiment, GetExperimentsParams>(method)
    const store = reactive({
      experiments: pagination.data,
      isLoading: pagination.isLoading,
      selectedExperiments: [],
      visibleColumns: [],
      queryParams: {},
      setTableColumns: vi.fn(),
      setVisibleColumns: vi.fn(),
      setQueryParams: vi.fn(),
      reset: pagination.reset,
      onLazyLoad: pagination.onLazyLoad,
    })
    vi.mocked(useExperimentsStore).mockReturnValue(
      store as unknown as ReturnType<typeof useExperimentsStore>,
    )
    const wrapper = shallowMount(ExperimentTable, mountingOptions)
    await pagination.getInitialPage()
    const request = pagination.getNextPage()
    await nextTick()

    expect(pagination.isLoading.value).toBe(true)
    expect(wrapper.findComponent({ name: 'DataTable' }).props('loading')).toBe(false)

    resolve({ items: [], cursor: null })
    await request
    wrapper.unmount()
  })
})
