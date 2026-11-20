export type SqlValue = number | string | Uint8Array | null
export type ParamsObject = Record<string, SqlValue>
export type BindParams = SqlValue[] | ParamsObject | null

export interface QueryExecResult {
  columns: string[]
  values: SqlValue[][]
}

/** The sql.js statement API the provider was written against. */
export interface SnapshotStatement {
  bind(values?: BindParams): boolean
  step(): boolean
  get(): SqlValue[]
  getAsObject(): ParamsObject
  free(): boolean
}

/** The sql.js database API the provider was written against. */
export interface SnapshotDatabase {
  exec(sql: string, params?: BindParams): QueryExecResult[]
  prepare(sql: string, params?: BindParams): SnapshotStatement
  close(): void
}
