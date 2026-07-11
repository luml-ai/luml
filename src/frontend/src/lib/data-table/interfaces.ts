export interface IDataTable {
  createFormCSV(file: File): Promise<void>
  downloadCSV(fileName: string): void
  getColumnsCount(): number
  getRowsCount(): number
  clearTable(): void
  getColumnNames(): string[]
  getObjects(): object[]
  setSelectedColumns(columns: string[]): void
  getSelectedColumns(): string[]
  setFilters(filters: FilterItem[]): void
  getFilters(): FilterItem[]
  getDataForTraining(): object
}

export enum FilterType {
  Equals = 'Equals',
  NotEquals = 'Not equals',
  LessThan = 'Less than',
  LessThanOrEqualTo = 'Less than or equal to',
  GreaterThan = 'Greater than',
  GreaterThanOrEqualTo = 'Greater than or equal to',
}

export interface FilterItem {
  id: number
  column: string
  filterType: FilterType
  parameter: string
}
