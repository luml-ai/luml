import { describe, it, expect } from 'vitest'
import { nextTick, ref } from 'vue'
import { useForecastSetup } from '../useForecastSetup'

const defaultColumns = ['date', 'sales', 'promo']
const defaultRows = [
  { date: new Date('2020-01-01'), sales: 1000, promo: 0 },
  { date: new Date('2020-02-01'), sales: 1100, promo: 1 },
  { date: new Date('2020-03-01'), sales: 1200, promo: 0 },
]

function createSetup(
  columns: string[] = defaultColumns,
  rows: Record<string, unknown>[] = defaultRows,
) {
  const columnsRef = ref(columns)
  const rowsRef = ref(rows)
  return { setup: useForecastSetup(columnsRef, rowsRef), columnsRef, rowsRef }
}

describe('useForecastSetup defaults', () => {
  it('detects the date column and picks the first non-date column as target', () => {
    const { setup } = createSetup()
    expect(setup.dateCol.value).toBe('date')
    expect(setup.targetCol.value).toBe('sales')
    expect(setup.frequency.value).toBe('month')
    expect(setup.isValid.value).toBe(true)
  })

  it('is invalid when no column parses as dates', () => {
    const { setup } = createSetup(
      ['a', 'b'],
      [
        { a: 1, b: 2 },
        { a: 3, b: 4 },
      ],
    )
    expect(setup.dateNotParseable.value).toBe(true)
    expect(setup.isValid.value).toBe(false)
  })
})

describe('useForecastSetup role actions', () => {
  it('reassigns roles and reports them per column', () => {
    const { setup } = createSetup()
    setup.setTargetColumn('promo')
    expect(setup.columnRole('date')).toBe('date')
    expect(setup.columnRole('promo')).toBe('target')
    expect(setup.columnRole('sales')).toBeNull()
  })

  it('ignores assigning the date role to the target column and vice versa', () => {
    const { setup } = createSetup()
    setup.setDateColumn('sales')
    setup.setTargetColumn('date')
    expect(setup.dateCol.value).toBe('date')
    expect(setup.targetCol.value).toBe('sales')
  })

  it('toggles auxiliary and known-future roles', () => {
    const { setup } = createSetup()
    setup.toggleAux('promo')
    expect(setup.columnRole('promo')).toBe('aux')

    setup.toggleKnownFuture('promo')
    expect(setup.columnRole('promo')).toBe('known_future')
    expect(setup.hasKnownFuture.value).toBe(true)

    setup.toggleKnownFuture('promo')
    expect(setup.columnRole('promo')).toBe('aux')

    setup.toggleAux('promo')
    expect(setup.columnRole('promo')).toBeNull()
  })

  it('ignores known-future toggles for non-auxiliary columns', () => {
    const { setup } = createSetup()
    setup.toggleKnownFuture('promo')
    expect(setup.knownFutureCols.value).toEqual([])
  })

  it('drops auxiliary and known-future roles when a column becomes the target', async () => {
    const { setup } = createSetup()
    setup.toggleAux('promo')
    setup.toggleKnownFuture('promo')
    setup.setTargetColumn('promo')
    await nextTick()
    expect(setup.auxCols.value).toEqual([])
    expect(setup.knownFutureCols.value).toEqual([])
  })
})

describe('useForecastSetup training preview', () => {
  it('rejects a preview end date before the last historical date', () => {
    const { setup } = createSetup()
    setup.previewEndDate.value = new Date('2020-02-15')
    expect(setup.previewDateInvalid.value).toBe(true)
    expect(setup.isValid.value).toBe(false)
  })

  it('computes the horizon for a preview date after the last history', () => {
    const { setup } = createSetup()
    setup.previewEndDate.value = new Date('2020-06-01')
    expect(setup.previewHorizon.value).toBe(3)
    expect(setup.config.value.preview_horizon).toBe(3)
  })

  it('sends no horizon when a known-future column exists', () => {
    const { setup } = createSetup()
    setup.toggleAux('promo')
    setup.toggleKnownFuture('promo')
    setup.previewEndDate.value = new Date('2020-06-01')
    expect(setup.previewHorizon.value).toBeNull()
    expect(setup.config.value.known_future_cols).toEqual(['promo'])
  })
})

describe('useForecastSetup column changes', () => {
  it('keeps selected roles when an unrelated column disappears', async () => {
    const { setup, columnsRef, rowsRef } = createSetup()
    setup.setTargetColumn('promo')
    columnsRef.value = ['date', 'promo']
    rowsRef.value = defaultRows.map(({ date, promo }) => ({ date, promo }))
    await nextTick()
    expect(setup.dateCol.value).toBe('date')
    expect(setup.targetCol.value).toBe('promo')
  })

  it('re-detects roles when the selected date column disappears', async () => {
    const { setup, columnsRef, rowsRef } = createSetup()
    columnsRef.value = ['sales', 'promo']
    rowsRef.value = defaultRows.map(({ sales, promo }) => ({ sales, promo }))
    await nextTick()
    expect(setup.dateCol.value).toBe('sales')
    expect(setup.targetCol.value).toBe('promo')
    expect(setup.isValid.value).toBe(false)
  })

  it('prunes auxiliary and known-future roles for hidden columns', async () => {
    const { setup, columnsRef, rowsRef } = createSetup()
    setup.toggleAux('promo')
    setup.toggleKnownFuture('promo')
    columnsRef.value = ['date', 'sales']
    rowsRef.value = defaultRows.map(({ date, sales }) => ({ date, sales }))
    await nextTick()
    expect(setup.auxCols.value).toEqual([])
    expect(setup.knownFutureCols.value).toEqual([])
  })
})
