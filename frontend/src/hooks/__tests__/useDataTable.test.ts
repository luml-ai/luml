import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useDataTable } from '@/hooks/useDataTable'
import { FilterType } from '@/lib/data-table/interfaces'

vi.mock('primevue', () => ({ useToast: () => ({ add: vi.fn() }) }))

const validator = () => ({ size: false, columns: false, rows: false })

async function detectColumnTypes(csv: string) {
  let table: ReturnType<typeof useDataTable> | undefined
  const wrapper = mount(
    defineComponent({
      setup() {
        table = useDataTable(validator)
        return {}
      },
      template: '<div />',
    }),
  )
  const file = { name: 'values.csv', size: csv.length, text: async () => csv } as File

  await table!.onSelectFile(file)
  await vi.waitFor(() => expect(Object.keys(table!.columnTypes.value)).not.toHaveLength(0))

  const columnTypes = { ...table!.columnTypes.value }
  wrapper.unmount()
  return columnTypes
}

describe('useDataTable column types', () => {
  it('detects a numeric column whose first value is zero', async () => {
    const csv = 'count,label\n0,first\n1,second'

    expect(await detectColumnTypes(csv)).toEqual({ count: 'number', label: 'string' })
  })

  it('detects a numeric column whose first value is empty', async () => {
    const csv = 'price,label\n,first\n1.5,second'

    expect(await detectColumnTypes(csv)).toEqual({ price: 'number', label: 'string' })
  })

  it('detects a date column', async () => {
    const csv = 'date,label\n2020-01-01,first\n2020-01-02,second'

    expect(await detectColumnTypes(csv)).toEqual({ date: 'date', label: 'string' })
  })

  it('keeps string columns with numeric-looking values as strings', async () => {
    const csv = 'code,label\n001,first\nSKU-2,second'

    expect(await detectColumnTypes(csv)).toEqual({ code: 'string', label: 'string' })
  })
})

describe('useDataTable state isolation', () => {
  const wrappers: ReturnType<typeof mount>[] = []

  function mountTable() {
    let table: ReturnType<typeof useDataTable> | undefined
    wrappers.push(
      mount(
        defineComponent({
          setup() {
            table = useDataTable(validator)
            return () => null
          },
        }),
      ),
    )
    return table!
  }

  afterEach(() => {
    wrappers.splice(0).forEach((wrapper) => wrapper.unmount())
  })

  it('keeps grouping separate for existing and newly mounted tables', () => {
    const first = mountTable()
    const second = mountTable()

    first.changeGroup('first_column')
    expect(second.getGroup.value).toEqual([])
    expect(mountTable().getGroup.value).toEqual([])

    second.changeGroup('second_column')
    expect(first.getGroup.value).toEqual(['first_column'])
    expect(second.getGroup.value).toEqual(['second_column'])
  })

  it('keeps mutable defaults separate on creation and after a reset', () => {
    const first = mountTable()
    const second = mountTable()
    const filter = { id: 1, column: 'feature', filterType: FilterType.Equals, parameter: '1' }

    first.selectedColumns.value.push('feature')
    first.getFilters.value.push(filter)
    first.columnTypes.value.feature = 'number'
    first.inputsOutputsColumns.value.push({ name: 'feature', variant: 'input' })

    expect(second.selectedColumns.value).toEqual([])
    expect(second.getFilters.value).toEqual([])
    expect(second.columnTypes.value).toEqual({})
    expect(second.inputsOutputsColumns.value).toEqual([])

    first.onRemoveFile()
    first.selectedColumns.value.push('other')
    first.getFilters.value.push(filter)
    first.columnTypes.value.other = 'string'
    const third = mountTable()

    for (const table of [second, third]) {
      expect(table.selectedColumns.value).toEqual([])
      expect(table.getFilters.value).toEqual([])
      expect(table.columnTypes.value).toEqual({})
      expect(table.inputsOutputsColumns.value).toEqual([])
    }
  })

  it('clears grouping on file removal and keeps subsequent resets empty', () => {
    const table = mountTable()
    table.changeGroup('old_column')
    table.onRemoveFile()
    expect(table.getGroup.value).toEqual([])

    table.changeGroup('new_column')
    table.onRemoveFile()
    expect(table.getGroup.value).toEqual([])
    expect(mountTable().getGroup.value).toEqual([])
  })

  it('clears grouping when switching files', async () => {
    const table = mountTable()
    table.changeGroup('old_column')
    const csv = 'feature,target\n1,2'
    await table.onSelectFile({ name: 'new.csv', size: csv.length, text: async () => csv } as File)
    await vi.waitFor(() => expect(table.isTableExist.value).toBe(true))

    expect(table.getGroup.value).toEqual([])
  })
})
