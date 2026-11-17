import sqlite3InitModule, {
  type BindingSpec,
  type Database as Sqlite3Database,
  type Sqlite3Static,
} from '@sqlite.org/sqlite-wasm'
import { RangeSnapshotDatabase } from '../../snapshot-source/RangeSqliteEngine'

/** A writable in-memory database behind the provider's sql.js adapter. */
export class MemoryDatabase extends RangeSnapshotDatabase {
  constructor(
    sqlite3: Sqlite3Static,
    private readonly writable: Sqlite3Database,
  ) {
    super(sqlite3, writable, (action) => action())
  }

  run(sql: string, params?: BindingSpec): void {
    this.writable.exec({ sql, ...(params ? { bind: params } : {}) })
  }
}

let sqlite3: Promise<Sqlite3Static> | null = null

export async function memoryDatabase(): Promise<MemoryDatabase> {
  sqlite3 ??= sqlite3InitModule()
  const loaded = await sqlite3
  return new MemoryDatabase(loaded, new loaded.oo1.DB(':memory:'))
}
