import { describe, expect, it } from 'vitest'
import sqlite3InitModule from '@sqlite.org/sqlite-wasm'
import { BufferRangeFile } from '../snapshot-source/httpSource'
import { RangeSqliteEngine } from '../snapshot-source/RangeSqliteEngine'
import type { SqlValue } from '../snapshot-source/SnapshotDatabase'

const PAGE_SIZE = 1024
const TAIL_BLOB_BYTES = 300
const TRUNCATED_BYTES = 200

/**
 * A database whose last page holds one row ending in a zero blob, behind enough pages of text
 * that a small page cache has to recycle buffers before that page is read.
 */
async function databaseEndingInZeros(): Promise<Uint8Array> {
  const sqlite3 = await sqlite3InitModule()
  const db = new sqlite3.oo1.DB(':memory:')
  db.exec(`
    PRAGMA page_size = ${PAGE_SIZE};
    CREATE TABLE filler (text TEXT);
    WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < 400)
      INSERT INTO filler SELECT printf('%.100c', char(65 + i % 26)) FROM n;
    CREATE TABLE tail (data BLOB);
    INSERT INTO tail VALUES (zeroblob(${TAIL_BLOB_BYTES}));
  `)
  const bytes = sqlite3.capi.sqlite3_js_db_export(db)
  db.close()
  return bytes
}

describe('RangeSqliteEngine', () => {
  const engine = RangeSqliteEngine.load()

  it('zero-fills a read that ends past the end of the file', async () => {
    const full = await databaseEndingInZeros()
    const truncated = full.slice(0, full.length - TRUNCATED_BYTES)
    const database = (await engine).openDatabase(new BufferRangeFile(truncated))

    database.exec('PRAGMA cache_size = 10')
    expect(database.exec('SELECT COUNT(*) FROM filler')[0]!.values).toEqual([[400]])
    const [tail] = database.exec('SELECT hex(data) FROM tail')
    expect(tail!.values).toEqual([['00'.repeat(TAIL_BLOB_BYTES)]])
  })
})

describe('RangeSqliteEngine sql.js adapter', () => {
  async function database() {
    return (await engine).openDatabase(new BufferRangeFile(await databaseEndingInZeros()))
  }
  const engine = RangeSqliteEngine.load()

  it('returns a result for every statement of an exec that yields rows', async () => {
    const db = await database()

    expect(db.exec("SELECT 1 AS a; SELECT 2 WHERE 0; SELECT ';' AS b, ? AS c", [7])).toEqual([
      { columns: ['a'], values: [[1]] },
      { columns: ['b', 'c'], values: [[';', 7]] },
    ])
    expect(db.exec('SELECT ? AS a; SELECT ? AS b; -- done', [5])).toEqual([
      { columns: ['a'], values: [[5]] },
      { columns: ['b'], values: [[5]] },
    ])
  })

  it('binds undefined as NULL', async () => {
    const db = await database()
    const values = [undefined, 1] as unknown as SqlValue[]

    expect(db.exec('SELECT ? IS NULL, ?', values)[0]!.values).toEqual([[1, 1]])
    const statement = db.prepare('SELECT :a IS NULL', { ':a': undefined } as never)
    statement.step()
    expect(statement.get()).toEqual([1])
    statement.free()
  })

  it('resets the statement and clears its bindings on bind() without values', async () => {
    const db = await database()
    const statement = db.prepare('SELECT ?', [5])

    expect(statement.step()).toBe(true)
    expect(statement.get()).toEqual([5])
    expect(statement.step()).toBe(false)
    expect(statement.bind()).toBe(true)
    expect(statement.step()).toBe(true)
    expect(statement.get()).toEqual([null])
    statement.free()
  })
})
