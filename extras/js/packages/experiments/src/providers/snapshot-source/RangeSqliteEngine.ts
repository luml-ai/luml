import sqlite3InitModule, {
  type BindingSpec,
  type Database as Sqlite3Database,
  type PreparedStatement,
  type SQLiteStruct,
  type Sqlite3Static,
  type SqlValue as Sqlite3Value,
  type WasmPointer,
} from '@sqlite.org/sqlite-wasm'
import type {
  BindParams,
  ParamsObject,
  QueryExecResult,
  SnapshotDatabase,
  SnapshotStatement,
  SqlValue,
} from './SnapshotDatabase'

export interface RangeFile {
  readonly size: number
  read(offset: number, length: number): Uint8Array
}

interface OpenRangeFile {
  file: RangeFile
  error: unknown
}

const VFS_NAME = 'luml-range'

// The VFS reads snapshots from memory or HTTP; the OPFS VFSes would only start a proxy worker.
const SQLITE3_API_CONFIG = {
  disable: { vfs: { opfs: true, 'opfs-vfs': true, 'opfs-wl': true, 'opfs-sahpool': true } },
}

// The package types omit the Emscripten options on purpose, but the build still honours them.
type InitWithOptions = (options?: {
  locateFile?: (file: string) => string
}) => Promise<Sqlite3Static>

// The published struct and VFS typings disagree with the runtime (member names, static
// structInfo, literal result codes), so VFS installation goes through these loose types.
type VfsArgument = number | bigint
type VfsMethods = Record<string, (...args: VfsArgument[]) => number>
type StructType = { structInfo: { sizeof: number } }
type InstallVfs = (options: {
  io: { struct: SQLiteStruct; methods: VfsMethods }
  vfs: { struct: SQLiteStruct; methods: VfsMethods }
}) => void

const DEFAULT_VFS_MEMBERS = [
  '$xRandomness',
  '$xSleep',
  '$xCurrentTime',
  '$xCurrentTimeInt64',
  '$xGetLastError',
] as const

function setStructMember(struct: SQLiteStruct, member: string, value: unknown): void {
  ;(struct as unknown as Record<string, unknown>)[member] = value
}

function toSqlJsValue(value: Sqlite3Value): SqlValue {
  if (typeof value === 'bigint') return Number(value)
  if (value instanceof Int8Array)
    return new Uint8Array(value.buffer, value.byteOffset, value.length)
  if (value instanceof ArrayBuffer) return new Uint8Array(value)
  return value
}

function toBinding(values: BindParams | undefined): BindingSpec | null {
  if (!values) return null
  if (Array.isArray(values)) return values.length ? values : null
  return Object.keys(values).length ? values : null
}

/** Splits SQL into statements at the semicolons that end one, as sqlite3_complete sees them. */
function splitStatements(sqlite3: Sqlite3Static, sql: string): string[] {
  const statements: string[] = []
  let pending = ''
  for (const part of sql.split(/(?<=;)/)) {
    pending += part
    if (sqlite3.capi.sqlite3_complete(pending)) {
      statements.push(pending)
      pending = ''
    }
  }
  if (pending.trim()) statements.push(pending)
  return statements
}

/*
 * Adapts the official build to the sql.js API the provider was written against. Two
 * differences are kept: integers beyond 32 bits bind as INTEGER (sql.js binds them as REAL,
 * which compares the same), and error messages carry the SQLite result code.
 */
class RangeStatement implements SnapshotStatement {
  constructor(
    private readonly statement: PreparedStatement,
    private readonly guard: <T>(action: () => T) => T,
  ) {}

  bind(values?: BindParams): boolean {
    this.statement.reset(true)
    const binding = toBinding(values)
    if (binding) this.statement.bind(binding)
    return true
  }

  step(): boolean {
    return this.guard(() => this.statement.step())
  }

  get(): SqlValue[] {
    return this.statement.get([]).map(toSqlJsValue)
  }

  getAsObject(): ParamsObject {
    const row = this.statement.get({})
    return Object.fromEntries(Object.entries(row).map(([key, value]) => [key, toSqlJsValue(value)]))
  }

  free(): boolean {
    this.statement.finalize()
    return true
  }
}

export class RangeSnapshotDatabase implements SnapshotDatabase {
  constructor(
    private readonly sqlite3: Sqlite3Static,
    private readonly database: Sqlite3Database,
    private readonly guard: <T>(action: () => T) => T,
  ) {}

  /** Like sql.js: every statement gets the parameters, each one with rows yields a result. */
  exec(sql: string, params?: BindParams): QueryExecResult[] {
    const binding = toBinding(params)
    return this.guard(() =>
      splitStatements(this.sqlite3, sql).flatMap((statement) =>
        this.execStatement(statement, binding),
      ),
    )
  }

  private execStatement(sql: string, binding: BindingSpec | null): QueryExecResult[] {
    let columns: string[] = []
    const values: SqlValue[][] = []
    // oo1 exec hands rows of the first statement with columns only, so each runs on its own.
    this.database.exec({
      sql,
      ...(binding ? { bind: binding } : {}),
      rowMode: 'stmt',
      callback: (statement: PreparedStatement) => {
        if (!values.length) columns = statement.getColumnNames()
        values.push(statement.get([]).map(toSqlJsValue))
      },
    })
    return values.length ? [{ columns, values }] : []
  }

  prepare(sql: string, params?: BindParams): SnapshotStatement {
    const statement = new RangeStatement(
      this.guard(() => this.database.prepare(sql)),
      this.guard,
    )
    statement.bind(params)
    return statement
  }

  close(): void {
    this.database.close()
  }
}

/**
 * Official SQLite wasm build with a synchronous, read-only VFS whose page reads come from
 * `RangeFile`s. sql.js exposes neither its Emscripten FS nor `sqlite3_vfs_register`, so it
 * cannot back a database with custom reads.
 */
export class RangeSqliteEngine {
  private readonly registered = new Map<string, OpenRangeFile>()
  private readonly open = new Map<WasmPointer, OpenRangeFile>()
  private nextFileId = 0

  private constructor(private readonly sqlite3: Sqlite3Static) {
    this.installVfs()
  }

  static async load(wasmUrl?: string): Promise<RangeSqliteEngine> {
    const init = sqlite3InitModule as unknown as InitWithOptions
    // The library reads and deletes this global during init; it is its documented config hook.
    ;(globalThis as { sqlite3ApiConfig?: unknown }).sqlite3ApiConfig = SQLITE3_API_CONFIG
    const sqlite3 = await init(wasmUrl ? { locateFile: () => wasmUrl } : undefined)
    return new RangeSqliteEngine(sqlite3)
  }

  openDatabase(file: RangeFile): SnapshotDatabase {
    const name = `snapshot-${this.nextFileId++}.db`
    const entry: OpenRangeFile = { file, error: null }
    const guard = <T>(action: () => T): T => {
      try {
        return action()
      } catch (error) {
        const cause = entry.error
        entry.error = null
        throw cause ?? error
      }
    }
    this.registered.set(name, entry)
    try {
      const database = guard(
        () =>
          new this.sqlite3.oo1.DB({
            filename: `file:${name}?immutable=1`,
            vfs: VFS_NAME,
            flags: 'r',
          }),
      )
      try {
        guard(() => database.exec('SELECT 1 FROM sqlite_master LIMIT 1'))
      } catch (error) {
        // Closing runs xClose, which releases the file (up to a whole downloaded member).
        database.close()
        throw error
      }
      return new RangeSnapshotDatabase(this.sqlite3, database, guard)
    } finally {
      this.registered.delete(name)
    }
  }

  private installVfs(): void {
    const { capi, wasm } = this.sqlite3
    if (capi.sqlite3_vfs_find(VFS_NAME)) return

    const io = new capi.sqlite3_io_methods()
    setStructMember(io, '$iVersion', 1)
    const vfs = new capi.sqlite3_vfs()
    const defaultVfs = new capi.sqlite3_vfs(capi.sqlite3_vfs_find(null))
    vfs.$iVersion = 2
    vfs.$szOsFile = (capi.sqlite3_file as unknown as StructType).structInfo.sizeof
    vfs.$mxPathname = 512
    vfs.$zName = wasm.allocCString(VFS_NAME, false)
    for (const member of DEFAULT_VFS_MEMBERS) {
      setStructMember(vfs, member, (defaultVfs as unknown as Record<string, unknown>)[member])
    }
    defaultVfs.dispose()

    const readOnly = () => capi.SQLITE_READONLY
    const ioMethods: VfsMethods = {
      xClose: (pFile) => {
        this.open.delete(pFile as WasmPointer)
        return 0
      },
      xRead: (pFile, pDest, amount, offset) =>
        this.read(pFile as WasmPointer, pDest as WasmPointer, Number(amount), Number(offset)),
      xWrite: readOnly,
      xTruncate: readOnly,
      xSync: () => 0,
      xFileSize: (pFile, pSize) => {
        wasm.poke64(
          pSize as WasmPointer,
          BigInt(this.open.get(pFile as WasmPointer)?.file.size ?? 0),
        )
        return 0
      },
      xLock: () => 0,
      xUnlock: () => 0,
      xCheckReservedLock: (_pFile, pOut) => {
        wasm.poke32(pOut as WasmPointer, 0)
        return 0
      },
      xFileControl: () => capi.SQLITE_NOTFOUND,
      xSectorSize: () => 512,
      xDeviceCharacteristics: () => capi.SQLITE_IOCAP_IMMUTABLE,
    }
    const vfsMethods: VfsMethods = {
      xOpen: (_pVfs, zName, pFile, _flags, pOutFlags) => {
        const name = zName ? wasm.cstrToJs(zName as WasmPointer) : null
        const entry = name ? this.registered.get(name) : undefined
        if (!entry) return capi.SQLITE_CANTOPEN
        this.open.set(pFile as WasmPointer, entry)
        const file = new capi.sqlite3_file(pFile as WasmPointer)
        file.$pMethods = io.pointer
        file.dispose()
        if (pOutFlags) wasm.poke32(pOutFlags as WasmPointer, capi.SQLITE_OPEN_READONLY)
        return 0
      },
      xDelete: readOnly,
      xAccess: (_pVfs, _zName, _flags, pOut) => {
        wasm.poke32(pOut as WasmPointer, 0)
        return 0
      },
      xFullPathname: (_pVfs, zName, size, pOut) =>
        wasm.cstrncpy(pOut as WasmPointer, zName as WasmPointer, Number(size)) < Number(size)
          ? 0
          : capi.SQLITE_CANTOPEN,
    }
    const installVfs = this.sqlite3.vfs.installVfs as unknown as InstallVfs
    installVfs({
      io: { struct: io, methods: ioMethods },
      vfs: { struct: vfs, methods: vfsMethods },
    })
  }

  private read(pFile: WasmPointer, pDest: WasmPointer, amount: number, offset: number): number {
    const { capi, wasm } = this.sqlite3
    const entry = this.open.get(pFile)
    if (!entry) return capi.SQLITE_IOERR_READ
    try {
      const bytes = entry.file.read(offset, amount)
      const heap = wasm.heap8u()
      heap.set(bytes, Number(pDest))
      if (bytes.length < amount) {
        heap.fill(0, Number(pDest) + bytes.length, Number(pDest) + amount)
        return capi.SQLITE_IOERR_SHORT_READ
      }
      return 0
    } catch (error) {
      // A JS exception must not unwind through wasm frames; it is rethrown by the database guard.
      entry.error = error
      return capi.SQLITE_IOERR_READ
    }
  }
}
