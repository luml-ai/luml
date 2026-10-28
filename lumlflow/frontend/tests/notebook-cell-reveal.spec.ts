import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, h } from 'vue'

import type { CellSummary } from '@/api/slices/workspace/workspace.interface'

vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: vi.fn() }),
}))
vi.mock('primevue/usetoast', () => ({ useToast: () => ({ add: vi.fn() }) }))

import NotebookBaseView from '@/components/notebooks/NotebookBaseView.vue'
import { useFlowStore } from '@/store/flow'

function summary(slug: string, order: string): CellSummary {
  return {
    slug,
    state: 'synced',
    primary: null,
    kinds: {},
    causes: [],
    reused: false,
    cost_seconds: null,
    order,
  } as unknown as CellSummary
}

const NotebookCellStub = defineComponent({
  props: { cell: { type: Object, required: true } },
  emits: ['click'],
  setup(props, { emit }) {
    return () =>
      h('div', {
        'data-slug': (props.cell as CellSummary).slug,
        onClick: () => emit('click'),
      })
  },
})

const CELL_TOPS: Record<string, number> = { alpha: 100, beta: 700, gamma: 1500 }
const WRAPPER_TOP = 60

let store: ReturnType<typeof useFlowStore>
let scrollTo: ReturnType<typeof vi.fn>
let animated: string[]
const mounted: VueWrapper[] = []

function rect(top: number): DOMRect {
  return { top } as DOMRect
}

function mountView(): VueWrapper {
  const wrapper = mount(NotebookBaseView, {
    attachTo: document.body,
    global: { stubs: { NotebookCell: NotebookCellStub } },
  })
  mounted.push(wrapper)
  return wrapper
}

beforeEach(() => {
  setActivePinia(createPinia())
  store = useFlowStore()
  store.cells = [summary('alpha', '1'), summary('beta', '2'), summary('gamma', '3')]

  scrollTo = vi.fn()
  animated = []
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (
    this: HTMLElement,
  ) {
    const slug = this.dataset.slug
    return rect(slug ? CELL_TOPS[slug]! : WRAPPER_TOP)
  })
  HTMLElement.prototype.scrollTo = scrollTo as unknown as HTMLElement['scrollTo']
  HTMLElement.prototype.animate = function (this: HTMLElement) {
    animated.push(this.dataset.slug ?? '')
    return {} as Animation
  }
})

afterEach(() => {
  mounted.splice(0).forEach((wrapper) => wrapper.unmount())
  vi.restoreAllMocks()
  delete (HTMLElement.prototype as Partial<HTMLElement>).scrollTo
  delete (HTMLElement.prototype as Partial<HTMLElement>).animate
})

describe('notebook cell reveal', () => {
  it('aligns the cell top to the top of the scroll area and highlights it', async () => {
    mountView()

    store.selectCell('beta')
    await flushPromises()

    expect(scrollTo).toHaveBeenCalledWith({ top: 700 - WRAPPER_TOP, behavior: 'smooth' })
    expect(animated).toEqual(['beta'])
  })

  it('reveals the already selected cell again when navigated to twice', async () => {
    mountView()

    store.selectCell('beta')
    await flushPromises()
    store.selectCell('beta')
    await flushPromises()

    expect(scrollTo).toHaveBeenCalledTimes(2)
    expect(animated).toEqual(['beta', 'beta'])
  })

  it('does not scroll when a cell is clicked inside the notebook', async () => {
    const wrapper = mountView()

    await wrapper.find('[data-slug="gamma"]').trigger('click')
    await flushPromises()

    expect(store.selectedCellId).toBe('gamma')
    expect(scrollTo).not.toHaveBeenCalled()
    expect(animated).toEqual([])
  })

  it('reveals a cell selected before the notebook view is mounted', async () => {
    store.selectCell('gamma')
    mountView()
    await flushPromises()

    expect(scrollTo).toHaveBeenCalledWith({ top: 1500 - WRAPPER_TOP, behavior: 'smooth' })
    expect(animated).toEqual(['gamma'])
  })

  it('does not replay a handled reveal when the notebook view is mounted again', async () => {
    const first = mountView()
    store.selectCell('alpha')
    await flushPromises()
    await first.find('[data-slug="beta"]').trigger('click')
    first.unmount()
    mounted.splice(mounted.indexOf(first), 1)
    scrollTo.mockClear()
    animated = []

    mountView()
    await flushPromises()

    expect(store.selectedCellId).toBe('beta')
    expect(scrollTo).not.toHaveBeenCalled()
    expect(animated).toEqual([])
  })
})
