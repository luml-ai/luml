import { fromCSV, type ColumnTable } from 'arquero'

export const dateOnlyCSVValues = new WeakSet<Date>()

export function parseCSV(text: string) {
  const table = fromCSV(text)
  let source: ColumnTable | undefined

  for (const column of table.columnNames()) {
    for (let row = 0; row < table.numRows(); row++) {
      const value = table.get(column, row)
      if (!(value instanceof Date)) continue

      // retain date-only provenance without changing timestamps used for export or training
      source ??= fromCSV(text, { autoType: false })
      if (/^\d{4}-\d{2}-\d{2}$/.test(source.get(column, row))) {
        dateOnlyCSVValues.add(value)
      }
    }
  }
  return table
}
