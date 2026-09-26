import { mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import { useDataTable } from '@/hooks/useDataTable'

vi.mock('primevue', () => ({ useToast: () => ({ add: vi.fn() }) }))

const validator = () => ({ size: false, columns: false, rows: false })

describe('useDataTable column types', () => {
  it('detects a numeric column whose first value is zero', async () => {
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
    const csv = 'count,label\n0,first\n1,second'
    const file = {
      name: 'values.csv',
      size: csv.length,
      text: async () => csv,
    } as File

    await table!.onSelectFile(file)
    await vi.waitFor(() => expect(table!.columnTypes.value).toHaveProperty('count'))

    expect(table!.columnTypes.value).toEqual({ count: 'number', label: 'string' })
    wrapper.unmount()
  })
})
