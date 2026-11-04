import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'

import type { TableBlock } from '@/api/slices/workspace/workspace.interface'

const assetPage = vi.hoisted(() => vi.fn())
vi.mock('@/api/slices/workspace/workspace.api', () => ({ workspaceApi: { assetPage } }))
vi.mock('primevue/usetoast', () => ({ useToast: () => ({ add: () => {} }) }))
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: () => {} }),
}))

import CellTableBlock from '@/components/notebooks/cell/preview/CellTableBlock.vue'
import { settle } from './fakes'

const preview: TableBlock = {
  block: 'table',
  columns: ['id', 'words'],
  dtypes: ['', ''],
  rows: [
    ['a', 1],
    ['b', 2],
  ],
  total_rows: 5,
} as unknown as TableBlock

function mountTable(props: Record<string, unknown> = { slug: 'articles', output: 'articles' }) {
  return mount(CellTableBlock, {
    props: { block: preview, ...props },
    global: { plugins: [PrimeVue] },
  })
}

function button(wrapper: ReturnType<typeof mountTable>) {
  return wrapper.findAll('button').find((found) => found.text().includes('Show more rows'))
}

beforeEach(() => {
  setActivePinia(createPinia())
  assetPage.mockReset()
})

describe('a table output longer than its preview', () => {
  it('offers the rest and appends it, matching columns by name', async () => {
    assetPage.mockResolvedValueOnce({
      page: {
        columns: ['words', 'id'],
        dtypes: ['', ''],
        rows: [
          [3, 'c'],
          [4, 'd'],
          [5, 'e'],
        ],
        offset: 2,
        total_rows: 5,
        total_columns: 2,
      },
    })
    const wrapper = mountTable()
    expect(wrapper.text()).toContain('2 of 5 rows')

    await button(wrapper)!.trigger('click')
    await settle()

    expect(assetPage).toHaveBeenCalledWith('articles.articles', 2, 100, undefined, undefined)
    expect(wrapper.text()).toContain('5 of 5 rows')
    expect(wrapper.findAll('tbody tr').map((row) => row.text())).toEqual([
      'a1',
      'b2',
      'c3',
      'd4',
      'e5',
    ])
    expect(button(wrapper)).toBeUndefined()
  })

  it('offers nothing when it cannot say which output it shows', () => {
    expect(button(mountTable({}))).toBeUndefined()
  })
})
