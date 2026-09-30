import { flushPromises, shallowMount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DataTable } from 'primevue'
import type { Artifact, GetArtifactsListResponse } from '@/lib/api/artifacts/interfaces'
import ArtifactsTable from './ArtifactsTable.vue'
import TableToolbar from './TableToolbar.vue'

const harness = vi.hoisted(() => ({
  getOrbitArtifacts: vi.fn(),
  getArtifactsExtraValues: vi.fn().mockResolvedValue([]),
  toastAdd: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  api: { artifacts: { getOrbitArtifacts: harness.getOrbitArtifacts } },
}))
vi.mock('@/stores/artifacts', async () => {
  const { reactive } = await import('vue')
  const store = reactive({
    artifactsList: [] as Artifact[],
    getArtifactsExtraValues: harness.getArtifactsExtraValues,
    setArtifactsList: (artifacts: Artifact[]) => {
      store.artifactsList = artifacts
    },
  })
  return { useArtifactsStore: () => store }
})
vi.mock('@/stores/collections', () => ({
  useCollectionsStore: () => ({ currentCollection: { id: 'models', type: 'model' } }),
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { organizationId: 'org', id: 'orbit' } }),
  useRouter: () => ({ push: vi.fn() }),
}))
vi.mock('primevue', async (importOriginal) => {
  const actual = await importOriginal<typeof import('primevue')>()
  const { defineComponent } = await import('vue')
  return {
    ...actual,
    DataTable: defineComponent({
      name: 'DataTable',
      inheritAttrs: false,
      props: ['selection', 'selectAll', 'virtualScrollerOptions', 'scrollHeight'],
      emits: ['update:selection', 'select-all-change'],
      template: '<div />',
    }),
    useToast: () => ({ add: harness.toastAdd }),
  }
})
vi.mock('./TableToolbar.vue', () => ({
  default: {
    name: 'TableToolbar',
    props: ['selectedArtifacts', 'loadingSelection'],
    emits: ['clearSelectedArtifacts', 'updateSelectedArtifacts'],
    template: '<div />',
  },
}))

function artifacts(start: number, count: number): Artifact[] {
  return Array.from({ length: count }, (_, index) => ({ id: `${start + index}` }) as Artifact)
}

function deferredPage() {
  let resolve!: (page: GetArtifactsListResponse) => void
  const promise = new Promise<GetArtifactsListResponse>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

describe('ArtifactsTable Pick All', () => {
  let wrapper: ReturnType<typeof shallowMount>
  const firstPage = artifacts(0, 20)
  const secondPage = artifacts(20, 20)
  const lastPage = artifacts(40, 5)

  beforeEach(() => {
    harness.getOrbitArtifacts
      .mockReset()
      .mockResolvedValueOnce({ items: firstPage, cursor: 'next' })
    harness.toastAdd.mockReset()
  })

  afterEach(() => wrapper?.unmount())

  async function mountTable() {
    wrapper = shallowMount(ArtifactsTable, {
      global: { stubs: { DataTable: false }, directives: { tooltip: vi.fn() } },
    })
    await flushPromises()
    return wrapper.findComponent(DataTable)
  }

  function selectedIds() {
    return wrapper
      .findComponent(TableToolbar)
      .props('selectedArtifacts')
      .map((artifact: Artifact) => artifact.id)
  }

  it('selects every collection page and keeps appended artifacts selected', async () => {
    harness.getOrbitArtifacts
      .mockResolvedValueOnce({ items: secondPage, cursor: 'last' })
      .mockResolvedValueOnce({ items: lastPage, cursor: null })
    const table = await mountTable()

    table.vm.$emit('select-all-change', { checked: true })
    await flushPromises()

    expect(selectedIds()).toEqual(artifacts(0, 45).map(({ id }) => id))
    expect(harness.getOrbitArtifacts.mock.calls.map((call) => call[2].cursor)).toEqual([
      null,
      'next',
      'last',
    ])
    expect(table.props('selectAll')).toBe(true)

    const { useArtifactsStore } = await import('@/stores/artifacts')
    useArtifactsStore().setArtifactsList([...artifacts(0, 45), ...artifacts(45, 1)])
    await flushPromises()
    expect(selectedIds()).toEqual(artifacts(0, 46).map(({ id }) => id))

    useArtifactsStore().setArtifactsList([])
    await flushPromises()
    useArtifactsStore().setArtifactsList(lastPage)
    await flushPromises()
    expect(selectedIds()).toEqual(artifacts(0, 46).map(({ id }) => id))
  })

  it.each(['header', 'toolbar'])(
    'stops selecting and loading after clearing from the %s',
    async (source) => {
      const pending = deferredPage()
      harness.getOrbitArtifacts.mockReturnValueOnce(pending.promise)
      const table = await mountTable()
      table.vm.$emit('select-all-change', { checked: true })
      await flushPromises()

      if (source === 'header') table.vm.$emit('select-all-change', { checked: false })
      else wrapper.findComponent(TableToolbar).vm.$emit('clearSelectedArtifacts')
      pending.resolve({ items: secondPage, cursor: 'last' })
      await flushPromises()

      expect(selectedIds()).toEqual([])
      expect(table.props('selectAll')).toBe(false)
      expect(harness.getOrbitArtifacts).toHaveBeenCalledTimes(2)
    },
  )

  it('keeps a manual deselection and does not select subsequent pages', async () => {
    const pending = deferredPage()
    harness.getOrbitArtifacts.mockReturnValueOnce(pending.promise)
    const table = await mountTable()
    table.vm.$emit('select-all-change', { checked: true })
    await flushPromises()

    table.vm.$emit('update:selection', firstPage.slice(1))
    pending.resolve({ items: secondPage, cursor: 'last' })
    await flushPromises()

    expect(selectedIds()).toEqual(firstPage.slice(1).map(({ id }) => id))
    expect(table.props('selectAll')).toBe(false)
    expect(harness.getOrbitArtifacts).toHaveBeenCalledTimes(2)
  })

  it('starts only one pagination loop when Pick All is canceled and selected again', async () => {
    const pending = deferredPage()
    harness.getOrbitArtifacts
      .mockReturnValueOnce(pending.promise)
      .mockResolvedValueOnce({ items: lastPage, cursor: null })
    const table = await mountTable()
    table.vm.$emit('select-all-change', { checked: true })
    await flushPromises()
    table.vm.$emit('select-all-change', { checked: false })
    table.vm.$emit('select-all-change', { checked: true })
    await flushPromises()
    pending.resolve({ items: secondPage, cursor: 'last' })
    await flushPromises()

    expect(selectedIds()).toEqual(artifacts(0, 45).map(({ id }) => id))
    expect(harness.getOrbitArtifacts).toHaveBeenCalledTimes(3)
  })

  it('waits for an in-flight scroll request without aborting or duplicating it', async () => {
    const pending = deferredPage()
    harness.getOrbitArtifacts
      .mockReturnValueOnce(pending.promise)
      .mockResolvedValueOnce({ items: lastPage, cursor: null })
    const table = await mountTable()
    const options = table.props('virtualScrollerOptions')
    if (!options?.onLazyLoad) throw new Error('Missing lazy load handler')
    void options.onLazyLoad({ first: 0, last: 20 })
    await flushPromises()

    table.vm.$emit('select-all-change', { checked: true })
    await flushPromises()
    expect(harness.getOrbitArtifacts).toHaveBeenCalledTimes(2)
    expect(wrapper.findComponent(TableToolbar).props('loadingSelection')).toBe(true)

    pending.resolve({ items: secondPage, cursor: 'last' })
    await flushPromises()
    expect(selectedIds()).toEqual(artifacts(0, 45).map(({ id }) => id))
    expect(harness.getOrbitArtifacts).toHaveBeenCalledTimes(3)
    expect(wrapper.findComponent(TableToolbar).props('loadingSelection')).toBe(false)
  })

  it('reports pagination failure and preserves the loaded selection for a retry', async () => {
    harness.getOrbitArtifacts
      .mockResolvedValueOnce({ items: secondPage, cursor: 'last' })
      .mockRejectedValueOnce(new Error('network'))
    const table = await mountTable()
    table.vm.$emit('select-all-change', { checked: true })
    await flushPromises()

    expect(selectedIds()).toEqual(artifacts(0, 40).map(({ id }) => id))
    expect(table.props('selectAll')).toBe(false)
    expect(wrapper.findComponent(TableToolbar).props('loadingSelection')).toBe(false)
    expect(harness.toastAdd).toHaveBeenCalledOnce()

    harness.getOrbitArtifacts.mockResolvedValueOnce({ items: lastPage, cursor: null })
    table.vm.$emit('select-all-change', { checked: true })
    await flushPromises()
    expect(selectedIds()).toEqual(artifacts(0, 45).map(({ id }) => id))
    expect(table.props('selectAll')).toBe(true)
  })
})
