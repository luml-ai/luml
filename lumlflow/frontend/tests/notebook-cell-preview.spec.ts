
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Tooltip from 'primevue/tooltip'

import type { PreviewBlock } from '@/api/slices/workspace/workspace.interface'

vi.mock('@/api/slices/workspace/workspace.api', () => ({ workspaceApi: {} }))
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: () => {} }),
}))

import {
  COMPACT_KV_ROWS,
  previewSections,
} from '@/components/notebooks/cell/preview/preview.helpers'
import CellPreviewBlocks from '@/components/notebooks/cell/preview/CellPreviewBlocks.vue'
import { useFlowStore } from '@/store/flow'
import { settle } from './fakes'

const heading = (text: string): PreviewBlock => ({ block: 'markdown', text: `**${text}**` })
const kv = (entries: Record<string, string | number>): PreviewBlock => ({ block: 'kv', entries })
const series = (name: string): PreviewBlock => ({
  block: 'series',
  name,
  points: [
    [0, 1],
    [1, 2],
  ],
  total_points: 2,
})

const PARAMS = Object.fromEntries(
  Array.from({ length: 12 }, (_, at) => [`param_${at}`, at % 2 ? 'balanced' : 'sqrt']),
)

describe('reading a preview as sections', () => {
  it('puts each heading on the block it introduces', () => {
    const sections = previewSections([
      heading('params'),
      kv({ model: 'SVC', kernel: 'rbf' }),
      heading('metrics'),
      kv({ accuracy: 0.97, f1: 0.98 }),
    ])
    expect(sections.map((section) => [section.kind, section.title])).toEqual([
      ['kv', 'params'],
      ['bars', 'metrics'],
    ])
  })

  it('draws series logged side by side as one chart', () => {
    const sections = previewSections([
      heading('loss'),
      series('train'),
      series('test'),
      kv({ a: 'x' }),
    ])
    expect(sections).toHaveLength(2)
    expect(sections[0]).toMatchObject({ kind: 'lines', title: 'loss' })
    expect(sections[0]?.kind === 'lines' && sections[0].series.map((line) => line.name)).toEqual([
      'train',
      'test',
    ])
  })

  it('keeps a lone value and a mixed list as a list, not a chart', () => {
    expect(previewSections([kv({ auc: 0.9 })])[0]?.kind).toBe('kv')
    expect(previewSections([kv({ auc: 0.9, model: 'SVC' })])[0]?.kind).toBe('kv')
  })

  it('keeps a heading nothing followed as text', () => {
    expect(previewSections([heading('notes')])).toEqual([
      { kind: 'markdown', title: null, block: { block: 'markdown', text: '**notes**' } },
    ])
  })
})

describe('the preview on a card', () => {
  const mounted: VueWrapper[] = []
  let store: ReturnType<typeof useFlowStore>

  function preview(blocks: PreviewBlock[], compact = true): VueWrapper {
    const wrapper = mount(CellPreviewBlocks, {
      props: { blocks, truncated: false, compact, slug: 'evaluate' },
      attachTo: document.body,
      global: {
        plugins: [PrimeVue],
        directives: { tooltip: Tooltip },
        stubs: {
          CellChart: {
            props: ['section', 'hidden'],
            template: `<div class="chart-stub" :data-hidden="[...hidden].join(',')" />`,
          },
        },
      },
    })
    mounted.push(wrapper)
    return wrapper
  }

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useFlowStore()
  })

  afterEach(() => {
    for (const wrapper of mounted.splice(0)) wrapper.unmount()
  })

  it('cuts a long list short beside a chart, and expands the cell on demand', async () => {
    const wrapper = preview([heading('params'), kv(PARAMS), heading('metrics'), kv({ a: 1, b: 2 })])
    expect(wrapper.findAll('.kv-name')).toHaveLength(COMPACT_KV_ROWS)

    await wrapper.find('[aria-label="Expand"]').trigger('click')
    expect(store.expandedCellId).toBe('evaluate')
  })

  it('shows the whole list when no chart shares the card, or off the canvas', () => {
    expect(preview([heading('params'), kv(PARAMS)]).findAll('.kv-name')).toHaveLength(12)
    expect(preview([kv(PARAMS), kv({ a: 1, b: 2 })], false).findAll('.kv-name')).toHaveLength(12)
    expect(
      preview([heading('params'), kv(PARAMS)])
        .find('[aria-label="Expand"]')
        .exists(),
    ).toBe(false)
  })

  it('leaves out the metrics switched off, once applied', async () => {
    const wrapper = preview([heading('metrics'), kv({ accuracy: 0.9, f1: 0.8, auc: 0.95 })])
    const hidden = () => wrapper.find('.chart-stub').attributes('data-hidden')
    expect(hidden()).toBe('')

    await wrapper.find('[aria-label="Choose metrics"]').trigger('click')
    await settle()
    expect(
      [...document.body.querySelectorAll('.filter-name')].map((name) => name.textContent),
    ).toEqual(['accuracy', 'f1', 'auc'])

    document.body.querySelectorAll<HTMLInputElement>('.filter-row input')[1]?.click()
    await settle()
    expect(hidden()).toBe('')

    const apply = [...document.body.querySelectorAll('button')].find(
      (button) => button.textContent?.trim() === 'Apply',
    )
    apply?.click()
    await settle()
    expect(hidden()).toBe('1')
  })

  it('offers no filter on a chart of one metric', () => {
    const wrapper = preview([series('loss')])
    expect(wrapper.find('[aria-label="Choose metrics"]').exists()).toBe(false)
  })
})
