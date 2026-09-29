import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import { useDataTable } from '@/hooks/useDataTable'

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
