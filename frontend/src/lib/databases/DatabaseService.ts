import type { DatabaseMetadata, LumlFile, Notebook } from './database.interfaces'
import { openDB, deleteDB, type IDBPDatabase } from 'idb'
import jszip from 'jszip'
import { saveAs } from 'file-saver'

const DATABASE_PREFIX = 'jl_'
const FILES_STORE = 'files'
const AVAILABLE_FILES_EXTENSIONS = ['.dfs', '.fnnx', '.pyfnx', '.luml']

class DatabaseServiceClass {
  async getDatabases() {
    if (!indexedDB.databases) {
      console.warn('indexedDB.databases() not supported')
      return []
    }
    return await indexedDB.databases()
  }

  async deleteDatabase(name: string) {
    await deleteDB(name, {
      blocked: () => {
        console.warn(`db ${name} blocked`)
      },
    })
  }

  async createDatabase(id: string, metadata: DatabaseMetadata) {
    const db = await openDB(DATABASE_PREFIX + id, 1, {
      upgrade(db) {
        db.createObjectStore('meta')
      },
    })
    await db.put('meta', metadata, 'info')
    db.close()
    return db
  }

  async getDatabaseInfo(name: string): Promise<Notebook> {
    let db = await openDB(name)
    if (db.objectStoreNames.contains('meta')) {
      const meta = await db.get('meta', 'info')
      const files = await this.getLumlFiles(db)
      const info = { name, version: db.version, ...meta, files }
      db.close()
      return info
    }
    const version = db.version
    db.close()
    db = await openDB(name, version + 1, {
      upgrade(upgradeDb) {
        if (!upgradeDb.objectStoreNames.contains('meta')) {
          upgradeDb.createObjectStore('meta')
        }
      },
    })
    db.close()
    return { name, version: db.version }
  }

  async getDatabasesWithMetadata(): Promise<Notebook[]> {
    const databases = await this.getDatabases()
    const filteredDatabases = databases.filter(
      (database) => database.name && database.name.startsWith(DATABASE_PREFIX),
    )
    const promises = filteredDatabases.map(async (database) => {
      if (!database.name) return database as Notebook
      const metadata = await DatabaseService.getDatabaseInfo(database.name)
      return { ...database, ...metadata }
    })
    return Promise.all(promises)
  }

  async editDatabase(name: string, metadata: DatabaseMetadata) {
    const version = await this.getVersion(name)
    const db = await openDB(name, version + 1, {
      upgrade(db) {
        if (!db.objectStoreNames.contains('meta')) {
          db.createObjectStore('meta')
        }
      },
    })
    await db.put('meta', metadata, 'info')
    db.close()
  }

  async createBackup(name: string) {
    const db = await openDB(name)
    const metadata = await this.getDatabaseInfo(name)
    const databaseName = metadata?.fullname || name
    if (!db.objectStoreNames.contains(FILES_STORE)) {
      db.close()
      throw new Error(`Database ${databaseName} not includes ${FILES_STORE} store`)
    }
    const tx = db.transaction(FILES_STORE, 'readonly')
    const store = tx.objectStore(FILES_STORE)
    const allFiles = await store.getAll()
    const zip = new jszip()

    for (const file of allFiles) {
      const filePath = file.path || file.name
      if (!filePath) continue

      if (
        file.type === 'directory' ||
        file.mimetype === 'application/x-directory' ||
        filePath.endsWith('/')
      ) {
        continue
      }

      const content = file.content ?? file.data ?? file.body

      if (content === undefined) {
        console.log(`Skipping ${filePath} - no content found`)
        continue
      }

      const format = file?.format || file?.type

      try {
        let fileData: string | Uint8Array | ArrayBuffer | Blob

        if (content instanceof Blob) {
          fileData = content
        } else if (content instanceof ArrayBuffer) {
          fileData = content
        } else if (content instanceof Uint8Array) {
          fileData = content
        } else if (
          format === 'json' ||
          (typeof content === 'object' && content !== null && !(content instanceof Date))
        ) {
          fileData = JSON.stringify(content, null, 2)
        } else if (typeof content === 'string') {
          fileData = content
        } else if (content === null || content === undefined || content === '') {
          fileData = ''
        } else {
          // Fallback: try to convert to string
          fileData = String(content)
        }

        const cleanPath = filePath.replace(/\/$/, '')

        zip.file(cleanPath, fileData)
      } catch (e) {
        console.error(`Failed to process file ${filePath}:`, e)
        continue
      }
    }

    const fileCount = Object.keys(zip.files).length
    if (fileCount === 0) {
      db.close()
      throw new Error('No files found to backup')
    }

    console.log(`Creating zip with ${fileCount} files`)

    const zipBlob = await zip.generateAsync({
      type: 'blob',
      compression: 'DEFLATE',
      compressionOptions: { level: 6 },
    })
    saveAs(zipBlob, `${databaseName}-backup.zip`)
    db.close()
  }

  async getFileBlob(file: LumlFile) {
    const byteCharacters = atob(file.content)
    const byteNumbers = new Array(byteCharacters.length)
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i)
    }
    const byteArray = new Uint8Array(byteNumbers)
    return new Blob([byteArray], { type: file.mimetype })
  }

  private async getVersion(name: string) {
    const databases = await indexedDB.databases()
    const found = databases.find((db) => db.name === name)
    return found?.version ?? 0
  }

  private async getLumlFiles(db: IDBPDatabase): Promise<LumlFile[]> {
    if (!db.objectStoreNames.contains(FILES_STORE)) return []
    const tx = db.transaction(FILES_STORE, 'readonly')
    const store = tx.objectStore(FILES_STORE)
    const allFiles = await store.getAll()
    const files = allFiles.filter((file) => {
      const fullPath = file?.path || file?.name || ''

      return AVAILABLE_FILES_EXTENSIONS.find((extension) => {
        return fullPath.endsWith(extension)
      })
    })

    return files.map((file) => ({
      ...file,
      name: file.path || file.name,
    }))
  }
}

export const DatabaseService = new DatabaseServiceClass()
