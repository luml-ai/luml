import { ColumnTable, fromCSV, escape } from 'arquero'
import { FilterType, type FilterItem, type IDataTable } from './interfaces'
import { Observable } from '@/utils/observable/Observable'

export type SelectTableEvent = { name: string; size: number } | null

export type Events = {
  SELECT_TABLE: SelectTableEvent
}

export class DataTableArquero extends Observable<Events> implements IDataTable {
  private dataTable: ColumnTable | null = null
  private selectedColumns: string[] = []
  private filters: FilterItem[] = []

  constructor() {
    super()
  }

  private getCurrentData() {
    if (!this.dataTable) throw new Error('You need createTable before')

    let data = this.dataTable
    if (this.filters.length)
      data = data.filter(escape((row: any) => this.filteredRow(row, this.filters)))
    if (this.selectedColumns.length) data = data.select(this.selectedColumns)
    return data
  }

  private filteredRow(row: any, filters: FilterItem[]) {
    return filters.every((filter) => {
      const columnValue = row[filter.column]
      const parameter = isNaN(filter.parameter as any) ? filter.parameter : +filter.parameter

      switch (filter.filterType) {
        case FilterType.Equals:
          return columnValue === parameter
        case FilterType.NotEquals:
          return columnValue !== parameter
        case FilterType.LessThan:
          return columnValue < parameter
        case FilterType.LessThanOrEqualTo:
          return columnValue <= parameter
        case FilterType.GreaterThan:
          return columnValue > parameter
        case FilterType.GreaterThanOrEqualTo:
          return columnValue >= parameter
        default:
          return true
      }
    })
  }

  async createFormCSV(file: File) {
    this.resetData()
    this.dataTable = fromCSV(await file.text())

    this.emit('SELECT_TABLE', { name: file.name, size: file.size })
  }

  async downloadCSV(fileName: string = 'output.csv') {
    const csvContent = this.getCurrentData().toCSV()

    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName
    a.style.display = 'none'
    document.body.appendChild(a)
    a.click()

    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  getColumnsCount(): number {
    return this.getCurrentData().numCols()
  }

  getRowsCount(): number {
    return this.getCurrentData().numRows()
  }

  clearTable(): void {
    this.resetData()
    this.emit('SELECT_TABLE', null)
  }

  getColumnNames() {
    return this.getCurrentData().columnNames()
  }

  getObjects() {
    return this.getCurrentData().objects()
  }

  setSelectedColumns(columns: string[]) {
    this.selectedColumns = columns
  }

  getSelectedColumns() {
    return this.selectedColumns
  }

  setFilters(filters: FilterItem[]) {
    this.filters = filters
  }

  getFilters(): FilterItem[] {
    return this.filters
  }

  getDataForTraining() {
    const data = this.getObjects().reduce((acc: Record<string, (string | number)[]>, object) => {
      for (const key in object) {
        const value = object[key as keyof typeof object]
        if (acc[key]) {
          acc[key].push(value)
        } else {
          acc[key] = [value]
        }
      }

      return acc
    }, {})
    return data
  }

  resetData() {
    this.dataTable = null
    this.selectedColumns = []
    this.filters = []
  }
}
