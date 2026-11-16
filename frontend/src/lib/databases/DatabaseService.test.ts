// @vitest-environment node
import 'fake-indexeddb/auto'
import { IDBDatabase, IDBFactory } from 'fake-indexeddb'
import { openDB, deleteDB } from 'idb'
import JSZip from 'jszip'
import { saveAs } from 'file-saver'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DatabaseService } from './DatabaseService'

vi.mock('file-saver', () => ({ saveAs: vi.fn() }))

const name = 'jl-notebook'
const metadata = { fullname: 'Notebook', createdAt: 1 }

beforeEach(() => {
  vi.stubGlobal('indexedDB', new IDBFactory())
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

async function createNotebook(withMetadata = false, withFiles = true) {
  const db = await openDB(name, 1, {
    upgrade(db) {
      if (withFiles) db.createObjectStore('files')
      if (withMetadata) db.createObjectStore('meta')
    },
  })
  if (withMetadata) await db.put('meta', metadata, 'info')
  return db
}

describe('notebook database operations', () => {
  it.each([false, true])('backs up files with metadata present: %s', async (withMetadata) => {
    const db = await createNotebook(withMetadata)
    await db.put('files', { path: 'example.py', content: 'print(1)' }, 'example.py')
    db.close()

    await DatabaseService.createBackup(name)

    expect(saveAs).toHaveBeenCalledOnce()
    const [blob, filename] = vi.mocked(saveAs).mock.calls[0]
    expect(filename).toBe(`${withMetadata ? metadata.fullname : name}-backup.zip`)
    const zip = await JSZip.loadAsync(await (blob as Blob).arrayBuffer())
    expect(await zip.file('example.py')?.async('string')).toBe('print(1)')
    await deleteDB(name)
  })

  it.each(['metadata', 'edit'] as const)(
    'reports a blocked %s upgrade and completes after the external connection closes',
    async (operation) => {
      const db = await createNotebook(operation === 'edit')
      const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
      const pending =
        operation === 'metadata'
          ? DatabaseService.getDatabaseInfo(name)
          : DatabaseService.editDatabase(name, { ...metadata, fullname: 'Renamed' })

      try {
        await vi.waitFor(() => expect(warn).toHaveBeenCalledWith(expect.stringContaining(name)))
      } finally {
        db.close()
        await pending
      }

      const updated = await openDB(name)
      expect(updated.objectStoreNames.contains('meta')).toBe(true)
      if (operation === 'edit') {
        expect(await updated.get('meta', 'info')).toEqual({ ...metadata, fullname: 'Renamed' })
      }
      updated.close()
      await deleteDB(name)
    },
  )

  it.each([false, true])(
    'closes a failed backup with files store present: %s',
    async (withFiles) => {
      const db = await createNotebook(true, withFiles)
      db.close()

      await expect(DatabaseService.createBackup(name)).rejects.toThrow(
        withFiles ? 'No files found to backup' : 'not includes files store',
      )

      expect(saveAs).not.toHaveBeenCalled()
      await deleteDB(name)
    },
  )

  it.each(['metadata', 'edit'] as const)(
    'closes the connection when a %s transaction fails',
    async (operation) => {
      const db = await createNotebook(true)
      db.close()
      const transaction = IDBDatabase.prototype.transaction
      vi.spyOn(IDBDatabase.prototype, 'transaction').mockImplementation(function (
        this: globalThis.IDBDatabase,
        ...args
      ) {
        if (args[1] === 'readonly' || args[1] === 'readwrite') {
          throw new Error('transaction failed')
        }
        return transaction.apply(this, args)
      })

      await expect(
        operation === 'metadata'
          ? DatabaseService.getDatabaseInfo(name)
          : DatabaseService.editDatabase(name, metadata),
      ).rejects.toThrow('transaction failed')

      await deleteDB(name)
    },
  )

  it('closes the backup connection when archive generation fails', async () => {
    const db = await createNotebook(true)
    await db.put('files', { path: 'example.py', content: 'print(1)' }, 'example.py')
    db.close()
    vi.spyOn(JSZip.prototype, 'generateAsync').mockRejectedValueOnce(new Error('archive failed'))

    await expect(DatabaseService.createBackup(name)).rejects.toThrow('archive failed')

    expect(saveAs).not.toHaveBeenCalled()
    await deleteDB(name)
  })
})
