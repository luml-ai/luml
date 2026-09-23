import { describe, expect, it } from 'vitest'
import { DataTableArquero } from './DataTableArquero'
import { FilterType, type FilterItem } from './interfaces'

function equalsFilter(column: string, parameter: string): FilterItem {
  return {
    id: 1,
    column,
    filterType: FilterType.Equals,
    parameter,
  }
}

async function createTable() {
  const table = new DataTableArquero()
  const file = {
    name: 'values.csv',
    size: 35,
    text: async () => 'code,value\n001,10\nSKU-2,0\n003,20',
  } as File

  await table.createFormCSV(file)
  return table
}

describe('DataTableArquero filters', () => {
  it('matches a string value without removing leading zeros', async () => {
    const table = await createTable()

    table.setFilters([equalsFilter('code', '001')])

    expect(table.getObjects()).toEqual([{ code: '001', value: 10 }])
  })

  it('does not interpret an empty filter as numeric zero', async () => {
    const table = await createTable()

    table.setFilters([equalsFilter('value', '')])

    expect(table.getObjects()).toEqual([])
  })

  it('converts filter text when comparing a numeric column', async () => {
    const table = await createTable()

    table.setFilters([equalsFilter('value', '10')])

    expect(table.getObjects()).toEqual([{ code: '001', value: 10 }])
  })
})
