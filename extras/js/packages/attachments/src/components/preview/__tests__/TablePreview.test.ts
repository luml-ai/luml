import { Blob as NodeBlob } from 'node:buffer'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { mount, flushPromises } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import DataTable from 'primevue/datatable'
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import TablePreview from '../TablePreview.vue'
import type { TablePreviewProps } from '../../../interfaces/interfaces'

function fixture(extension: string, name = 'samples'): Blob {
  const bytes = readFileSync(resolve(import.meta.dirname, 'fixtures', `${name}.${extension}`))
  return new Blob([new Uint8Array(bytes)])
}

function preview(props: TablePreviewProps) {
  return mount(TablePreview, { props, global: { plugins: [[PrimeVue, { unstyled: true }]] } })
}

beforeEach(() => {
  vi.stubGlobal('Blob', NodeBlob)
  vi.stubGlobal('matchMedia', () => ({
    matches: false,
    addEventListener() {},
    removeEventListener() {},
  }))
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('table previews', () => {
  it.each(['arrow', 'parquet'])(
    'paginates the first 1,000 rows of a %s file',
    { timeout: 15000 },
    async (extension) => {
      const blob = fixture(extension)
      const slice = vi.spyOn(blob, 'slice')
      const readWholeBlob = vi.spyOn(blob, 'arrayBuffer')
      const wrapper = preview({ fileName: `samples.${extension}`, contentBlob: blob })
      try {
        await vi.dynamicImportSettled()
        await vi.waitFor(() => expect(wrapper.find('tbody td').exists()).toBe(true), {
          timeout: 10000,
        })
        expect(wrapper.text()).toContain('Showing first 1,000 of 1,024 rows')
        const table = wrapper.getComponent(DataTable)
        expect(table.props('value')).toHaveLength(1000)
        expect(table.props('totalRecords')).toBe(1000)

        expect(wrapper.findAll('thead th').map((cell) => cell.text())).toEqual([
          'sample.id',
          'score',
        ])
        expect(wrapper.findAll('tbody tr')).toHaveLength(10)
        expect(wrapper.findAll('tbody tr')[0]?.text()).toContain('9007199254740993')
        await wrapper.get('[aria-label="Next Page"]').trigger('click')
        expect(wrapper.get('tbody td').text()).toBe('10')
        await wrapper.get('[aria-label="Last Page"]').trigger('click')
        expect(wrapper.findAll('tbody tr:last-child td').map((cell) => cell.text())).toEqual([
          '999',
          '',
        ])
        if (extension === 'parquet') {
          expect(readWholeBlob).not.toHaveBeenCalled()
          const requestedBytes = slice.mock.calls.reduce(
            (sum, [start = 0, end = blob.size]) => sum + end - start,
            0,
          )
          expect(requestedBytes).toBeGreaterThan(0)
          expect(requestedBytes).toBeLessThan(blob.size)
        }
      } finally {
        wrapper.unmount()
      }
    },
  )

  it('reads a prefix of an unindexed multi-page row group and preserves its exact decimal', async () => {
    const blob = fixture('parquet', 'pages')
    let bytes = 0
    const wrapper = preview({
      fileName: 'pages.parquet',
      parquetFile: {
        byteLength: blob.size,
        slice(start, end = blob.size) {
          bytes += end - start
          return blob.slice(start, end).arrayBuffer()
        },
      },
    })
    try {
      await vi.waitFor(() => expect(wrapper.text()).toContain('Showing first 1,000 of 16,384 rows'))
      expect(
        wrapper
          .findAll('tbody tr')[0]!
          .findAll('td')
          .map((cell) => cell.text()),
      ).toEqual(['0', '9007199254740993.01'])
      await wrapper.get('[aria-label="Last Page"]').trigger('click')
      expect(wrapper.get('tbody tr:last-child td').text()).toBe('999')
      expect(bytes).toBeLessThan(blob.size / 3)
    } finally {
      wrapper.unmount()
    }
  })

  it.each(['arrow', 'parquet'])(
    'keeps distinct microsecond and nanosecond %s timestamps',
    async (ext) => {
      const wrapper = preview({
        fileName: 'timestamps.' + ext,
        contentBlob: fixture(ext, 'timestamps'),
      })
      try {
        await vi.dynamicImportSettled()
        await vi.waitFor(() =>
          expect(wrapper.findAll('tbody td').map((cell) => cell.text())).toEqual([
            '1970-01-01T00:00:01.234567Z',
            '1969-12-31T23:59:59.999999998Z',
            '1970-01-01T00:00:01.234568Z',
            '1969-12-31T23:59:59.999999999Z',
          ]),
        )
      } finally {
        wrapper.unmount()
      }
    },
  )

  it.each(['lz4', 'zstd'])(
    'displays distinct same-name fields, decimals and timestamps from %s IPC',
    async (codec) => {
      const wrapper = preview({ fileName: 'report.arrow', contentBlob: fixture('arrow', codec) })
      try {
        await vi.waitFor(() =>
          expect(wrapper.findAll('tbody td').map((cell) => cell.text())).toEqual([
            '1',
            '2',
            '-12.34',
            '2026-01-01T00:00:00.000000Z',
          ]),
        )
        expect(wrapper.findAll('thead th').map((cell) => cell.text())).toEqual([
          'id',
          'id',
          'amount',
          'when',
        ])
      } finally {
        wrapper.unmount()
      }
    },
  )

  it('reads large-list values including inline and out-of-line strings and exact integers', async () => {
    const wrapper = preview({ fileName: 'lists.arrow', contentBlob: fixture('arrow', 'lists') })
    try {
      await vi.waitFor(() =>
        expect(wrapper.findAll('tbody td').map((cell) => cell.text())).toEqual([
          '["short","a non-inlined string"]',
          '["9007199254740993"]',
          '',
          '',
          '[]',
          '[]',
        ]),
      )
    } finally {
      wrapper.unmount()
    }
  })

  it('reads a range-backed Parquet file and displays the split total', async () => {
    const blob = fixture('parquet')
    const wrapper = preview({
      fileName: 'train.parquet',
      parquetFile: {
        byteLength: blob.size,
        slice: (start: number, end?: number) => blob.slice(start, end).arrayBuffer(),
      },
      totalRows: 40500,
    })
    try {
      await vi.waitFor(() => expect(wrapper.text()).toContain('Showing first 1,000 of 40,500 rows'))
      await wrapper.setProps({ totalRows: -1 })
      expect(wrapper.text()).toContain('Showing first 1,000 rows')
    } finally {
      wrapper.unmount()
    }
  })

  it('preserves full CSV pagination and omits the footer for regular CSV and XML', async () => {
    const csv = ['id', ...Array.from({ length: 1010 }, (_, index) => String(index))].join('\n')
    const wrapper = preview({ fileName: 'all.csv', contentBlob: new Blob([csv]) })
    try {
      await flushPromises()
      expect(wrapper.getComponent(DataTable).props('value')).toHaveLength(1010)
      expect(wrapper.text()).not.toContain('Showing first')

      await wrapper.setProps({ totalRows: 2000 })
      await flushPromises()
      expect(wrapper.getComponent(DataTable).props('value')).toHaveLength(1000)
      expect(wrapper.text()).toContain('Showing first 1,000 of 2,000 rows')

      await wrapper.setProps({
        totalRows: undefined,
        fileName: 'all.xml',
        contentBlob: new Blob(['<rows><row><id>four</id></row></rows>']),
      })
      await flushPromises()
      expect(wrapper.get('tbody td').text()).toBe('four')
      expect(wrapper.text()).not.toContain('Showing first')
    } finally {
      wrapper.unmount()
    }
  })

  it('ignores a read that finishes after the user selects another file', async () => {
    let finish!: (result: ArrayBuffer) => void
    const pending = new Promise<ArrayBuffer>((resolve) => {
      finish = resolve
    })
    const slice = vi.fn(() => pending)
    const wrapper = preview({
      fileName: 'slow.parquet',
      parquetFile: { byteLength: 9000, slice },
    })
    try {
      await vi.waitFor(() => expect(slice).toHaveBeenCalled())
      await wrapper.setProps({
        fileName: 'new.csv',
        parquetFile: undefined,
        contentBlob: new Blob(['name\nnew table']),
      })
      await flushPromises()
      finish(new ArrayBuffer(8))
      await flushPromises()
      expect(wrapper.get('tbody td').text()).toBe('new table')
      expect(wrapper.find('.error').exists()).toBe(false)
    } finally {
      wrapper.unmount()
    }
  })
})
