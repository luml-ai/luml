import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

import type { OpenFlow, OpenFlowsListing } from '@/api/slices/workspace/workspace.interface'
import type { StreamFrame } from '@/api/streams/flow'

vi.mock('@/api/slices/workspace/workspace.api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/slices/workspace/workspace.api')>()),
  workspaceApi: {
    listFlows: vi.fn(async (directory?: string) => ({ directory: directory ?? '/p', flows: [] })),
    openFlows: vi.fn(),
    openFlow: vi.fn(async () => ({
      flow: 'churn',
      flow_id: 'f-churn',
      path: '/p/churn.flow',
      kernel: { state: 'stopped', restart_required: false, behind: [] },
    })),
    restartKernel: vi.fn(async () => ({
      flow: 'churn',
      kernel: { state: 'running', restart_required: false, behind: [] },
    })),
    tree: vi.fn(async () => ({ flow: 'churn', branches: [], agent_sessions: [] })),
    getSettings: vi.fn(async () => ({
      flow: 'churn',
      settings: { reactivity: 'auto', eager_cost_threshold_s: 5 },
    })),
  },
}))
const streams = vi.hoisted(() => [] as { watched: string | null; closed: boolean }[])
vi.mock('@/api/streams/flow', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/streams/flow')>()),
  streamToken: () => 'token',
  FlowStream: class {
    record = { watched: null as string | null, closed: false }
    constructor() {
      streams.push(this.record)
    }
    onFrame() {
      return () => {}
    }
    connect() {}
    watchJournal(path: string) {
      this.record.watched = path
    }
    close() {
      this.record.closed = true
    }
  },
}))
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: vi.fn() }),
  useConfirm: () => ({ require: vi.fn() }),
}))
vi.mock('primevue/usetoast', () => ({ useToast: () => ({ add: vi.fn() }) }))

import { workspaceApi } from '@/api/slices/workspace/workspace.api'
import WorkspaceFolderItem from '@/components/workspace/folder/WorkspaceFolderItem.vue'
import WorkspaceFolderItemFlow from '@/components/workspace/folder/WorkspaceFolderItemFlow.vue'
import FlowStateMarker from '@/components/workspace/FlowStateMarker.vue'
import { useFlowStore } from '@/store/flow'
import { useWorkspaceStore } from '@/store/workspace'
import { settle } from './fakes'

const mocked = workspaceApi as unknown as Record<string, ReturnType<typeof vi.fn>>

function openFlow(overrides: Partial<OpenFlow> = {}): OpenFlow {
  return {
    flow: 'churn',
    path: '/p/churn.flow',
    relative_path: 'churn.flow',
    inside: true,
    kernel: 'stopped',
    active_runs: 0,
    leased_sessions: 0,
    stream_subscribers: 1,
    checked_out: true,
    last_activity: null,
    ...overrides,
  }
}

function listing(flows: OpenFlow[]): OpenFlowsListing {
  return {
    directory: '/p',
    flows,
    totals: {
      open_flows: flows.length,
      running_kernels: flows.filter((flow) => flow.kernel === 'running').length,
      active_runs: flows.reduce((sum, flow) => sum + flow.active_runs, 0),
      leased_sessions: flows.reduce((sum, flow) => sum + flow.leased_sessions, 0),
    },
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => (resolve = done))
  return { promise, resolve }
}

function opened(path: string, kernel: 'running' | 'stopped') {
  return {
    flow: path,
    flow_id: `f-${path}`,
    path,
    kernel: { state: kernel, restart_required: false, behind: [] },
  }
}

beforeEach(() => {
  setActivePinia(createPinia())
  streams.length = 0
  mocked.openFlows!.mockReset()
  mocked.openFlows!.mockResolvedValue(listing([]))
})

afterEach(() => {
  vi.useRealTimers()
})

describe('open flows in the workspace store', () => {
  it('maps open flows by path and keeps the totals', async () => {
    mocked.openFlows!.mockResolvedValue(
      listing([
        openFlow({ kernel: 'running', active_runs: 2 }),
        openFlow({ flow: 'far', path: '/q/far.flow', relative_path: null, inside: false }),
      ]),
    )
    const store = useWorkspaceStore()

    await store.fetchOpenFlows()

    expect(store.openFlowsByPath.get('/p/churn.flow')?.active_runs).toBe(2)
    expect(store.openFlowsByPath.has('/q/far.flow')).toBe(true)
    expect(store.openFlowsElsewhere.map((flow) => flow.path)).toEqual(['/q/far.flow'])
    expect(store.openFlowsTotals).toMatchObject({ open_flows: 2, running_kernels: 1 })
  })

  it('asks for the listed directory whenever the listing changes', async () => {
    vi.useFakeTimers()
    const store = useWorkspaceStore()
    const fetched = store.fetchDirectory('/p')
    await vi.runAllTimersAsync()
    await fetched

    expect(mocked.openFlows).toHaveBeenLastCalledWith('/p')
  })

  it('keeps the last answer when a poll fails', async () => {
    mocked.openFlows!.mockResolvedValueOnce(listing([openFlow()]))
    const store = useWorkspaceStore()
    await store.fetchOpenFlows()

    mocked.openFlows!.mockRejectedValueOnce(new Error('daemon away'))
    await store.fetchOpenFlows()

    expect(store.openFlowsByPath.size).toBe(1)
  })

  it('lets the newest request win when answers arrive out of order', async () => {
    const first = deferred<OpenFlowsListing>()
    const second = deferred<OpenFlowsListing>()
    mocked.openFlows!.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    const store = useWorkspaceStore()

    const older = store.fetchOpenFlows()
    const newer = store.fetchOpenFlows()
    second.resolve(listing([openFlow({ path: '/p/new.flow' })]))
    await newer
    first.resolve(listing([openFlow({ path: '/p/old.flow' })]))
    await older

    expect([...store.openFlowsByPath.keys()]).toEqual(['/p/new.flow'])
  })

  it("forgets the last directory's open flows as soon as another is asked for", async () => {
    vi.useFakeTimers()
    mocked.openFlows!.mockResolvedValueOnce(listing([openFlow()]))
    const store = useWorkspaceStore()
    store.currentDirectory = '/p'
    await store.fetchOpenFlows()

    mocked.openFlows!.mockReturnValue(new Promise(() => {}))
    const same = store.fetchDirectory('/p')
    expect(store.openFlowsByPath.size).toBe(1)
    await vi.runAllTimersAsync()
    await same
    expect(store.openFlowsByPath.size).toBe(1)

    const moved = store.fetchDirectory('/q')
    expect(store.openFlowsByPath.size).toBe(0)
    expect(store.openFlowsTotals.open_flows).toBe(0)
    await vi.runAllTimersAsync()
    await moved
  })

  it('groups open flows under the folders of the listing', async () => {
    mocked.openFlows!.mockResolvedValue(
      listing([
        openFlow({ path: '/p/team/a.flow', relative_path: 'team/a.flow', kernel: 'running' }),
        openFlow({ path: '/p/team/deep/b.flow', relative_path: 'team/deep/b.flow' }),
        openFlow(),
      ]),
    )
    const store = useWorkspaceStore()
    store.currentDirectory = '/p'
    await store.fetchOpenFlows()

    expect(store.openFlowsByFolder.get('/p/team')?.map((flow) => flow.path)).toEqual([
      '/p/team/a.flow',
      '/p/team/deep/b.flow',
    ])
    expect(store.openFlowsByFolder.size).toBe(1)
  })
})

describe('kernel state in the flow store', () => {
  it('follows kernel_state frames and the restart answer', async () => {
    const flowStore = useFlowStore()
    const frame = (kernel: 'running' | 'stopped'): StreamFrame => ({
      channel: 'journal',
      type: 'kernel',
      flow: '/p/churn.flow',
      step: 1,
      event: 'kernel_state',
      kernel,
    })

    flowStore.receiveLiveFrame(frame('running'))
    expect(flowStore.kernelState).toBe('running')
    flowStore.receiveLiveFrame(frame('stopped'))
    expect(flowStore.kernelState).toBe('stopped')

    flowStore.currentFlow = '/p/churn.flow'
    await flowStore.restartKernel()
    expect(mocked.restartKernel).toHaveBeenLastCalledWith('/p/churn.flow')
    expect(flowStore.kernelState).toBe('running')
  })

  it('does not restart without a flow, and clears the busy state on failure', async () => {
    const flowStore = useFlowStore()
    mocked.restartKernel!.mockClear()
    await flowStore.restartKernel()
    expect(mocked.restartKernel).not.toHaveBeenCalled()

    flowStore.currentFlow = '/p/churn.flow'
    mocked.restartKernel!.mockRejectedValueOnce(new Error('kernel would not stop'))
    await expect(flowStore.restartKernel()).rejects.toThrow('kernel would not stop')
    expect(flowStore.isKernelRestarting).toBe(false)
  })

  it("keeps only the latest flow's stream when opens resolve out of order", async () => {
    const openA = deferred<ReturnType<typeof opened>>()
    mocked.openFlow!.mockReturnValueOnce(openA.promise)
    mocked.openFlow!.mockResolvedValueOnce(opened('/p/b.flow', 'running'))
    const flowStore = useFlowStore()

    flowStore.setFlow('/p/a.flow')
    flowStore.setFlow('/p/b.flow')
    await settle()
    openA.resolve(opened('/p/a.flow', 'stopped'))
    await settle()

    expect(flowStore.kernelState).toBe('running')
    expect(streams.filter((stream) => !stream.closed).map((stream) => stream.watched)).toEqual([
      '/p/b.flow',
    ])
    expect(streams.some((stream) => stream.watched === '/p/a.flow')).toBe(false)
  })

  it('keeps exactly one stream through A, B and back to A', async () => {
    const firstA = deferred<ReturnType<typeof opened>>()
    const toB = deferred<ReturnType<typeof opened>>()
    const secondA = deferred<ReturnType<typeof opened>>()
    mocked
      .openFlow!.mockReturnValueOnce(firstA.promise)
      .mockReturnValueOnce(toB.promise)
      .mockReturnValueOnce(secondA.promise)
    const flowStore = useFlowStore()

    flowStore.setFlow('/p/a.flow')
    flowStore.setFlow('/p/b.flow')
    flowStore.setFlow('/p/a.flow')
    firstA.resolve(opened('/p/a.flow', 'stopped'))
    toB.resolve(opened('/p/b.flow', 'running'))
    secondA.resolve(opened('/p/a.flow', 'stopped'))
    await settle()

    const open = streams.filter((stream) => !stream.closed)
    expect(open.map((stream) => stream.watched)).toEqual(['/p/a.flow'])
  })

  it("does not show another flow's restart as loading", async () => {
    const restart = deferred<{ flow: string; kernel: { state: 'running' } }>()
    mocked.restartKernel!.mockReturnValueOnce(restart.promise)
    const flowStore = useFlowStore()
    flowStore.currentFlow = '/p/a.flow'

    const restarting = flowStore.restartKernel()
    expect(flowStore.isKernelRestarting).toBe(true)
    flowStore.setFlow('/p/b.flow')
    expect(flowStore.isKernelRestarting).toBe(false)

    restart.resolve({ flow: '/p/a.flow', kernel: { state: 'running' } })
    await restarting
    expect(flowStore.isKernelRestarting).toBe(false)
    expect(flowStore.kernelState).not.toBe('running')
  })
})

describe('the flow row marker', () => {
  const ITEM = {
    id: '/p/churn.flow',
    name: 'churn.flow',
    type: 'flow',
    path: '/p/churn.flow',
    size: 0,
  } as const

  async function row(flows: OpenFlow[]) {
    mocked.openFlows!.mockResolvedValue(listing(flows))
    await useWorkspaceStore().fetchOpenFlows()
    return mount(WorkspaceFolderItemFlow, {
      props: { item: ITEM },
      global: { stubs: { RouterLink: true } },
    })
  }

  it('shows nothing for a closed flow', async () => {
    const wrapper = await row([])
    expect(wrapper.find('.marker').exists()).toBe(false)
  })

  function tooltip(wrapper: ReturnType<typeof mount>): string {
    const marker = wrapper.findComponent(FlowStateMarker)
    return (marker.vm as unknown as { tooltip: string }).tooltip
  }

  it('shows a neutral dot for an open flow whose kernel is stopped', async () => {
    const wrapper = await row([openFlow()])
    expect(tooltip(wrapper)).toBe('Kernel stopped')
    expect(wrapper.find('.marker-dot--running').exists()).toBe(false)
    expect(wrapper.find('.marker').text()).toBe('')
  })

  it('highlights a running kernel and counts its runs', async () => {
    const wrapper = await row([openFlow({ kernel: 'running', active_runs: 3 })])
    expect(wrapper.find('.marker-dot--running').exists()).toBe(true)
    expect(wrapper.find('.marker-label').text()).toBe('3')
    expect(tooltip(wrapper)).toBe('Kernel running · 3 runs')
  })

  it('marks an agent holding the flow', async () => {
    const wrapper = await row([openFlow({ kernel: 'running', leased_sessions: 1 })])
    expect(wrapper.find('.marker-label').exists()).toBe(false)
    expect(wrapper.find('.marker-agent').exists()).toBe(true)
    expect(tooltip(wrapper)).toBe('Kernel running · 1 agent')
  })

  it('sums the open flows beneath a folder', async () => {
    mocked.openFlows!.mockResolvedValue(
      listing([
        openFlow({ path: '/p/team/a.flow', relative_path: 'team/a.flow' }),
        openFlow({ path: '/p/team/b.flow', relative_path: 'team/b.flow', kernel: 'running' }),
      ]),
    )
    const store = useWorkspaceStore()
    store.currentDirectory = '/p'
    await store.fetchOpenFlows()
    const wrapper = mount(WorkspaceFolderItem, {
      props: { item: { id: '/p/team', name: 'team', type: 'folder', path: '/p/team', size: 0 } },
    })

    expect(wrapper.find('.marker-label').exists()).toBe(false)
    expect(wrapper.find('.marker-dot--running').exists()).toBe(true)
    expect(tooltip(wrapper)).toBe('2 open flows · kernel running')
  })
})
