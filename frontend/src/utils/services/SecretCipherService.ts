import { openDB } from 'idb'

const ENCRYPTED_PREFIX = 'enc:v1:'
const DATABASE_NAME = 'luml_secrets'
const KEYS_STORE = 'keys'
const IV_LENGTH = 12

export interface CryptoKeyStore {
  get(id: string): Promise<CryptoKey | undefined>
  set(id: string, key: CryptoKey): Promise<void>
  delete(id: string): Promise<void>
}

class IndexedDbCryptoKeyStore implements CryptoKeyStore {
  private open() {
    return openDB(DATABASE_NAME, 1, {
      upgrade(db) {
        db.createObjectStore(KEYS_STORE)
      },
    })
  }

  async get(id: string) {
    const db = await this.open()
    try {
      return (await db.get(KEYS_STORE, id)) as CryptoKey | undefined
    } finally {
      db.close()
    }
  }

  async set(id: string, key: CryptoKey) {
    const db = await this.open()
    try {
      await db.put(KEYS_STORE, key, id)
    } finally {
      db.close()
    }
  }

  async delete(id: string) {
    const db = await this.open()
    try {
      await db.delete(KEYS_STORE, id)
    } finally {
      db.close()
    }
  }
}

function toBase64(bytes: Uint8Array) {
  let binary = ''
  for (const byte of bytes) binary += String.fromCharCode(byte)
  return btoa(binary)
}

function fromBase64(value: string) {
  return Uint8Array.from(atob(value), (char) => char.charCodeAt(0))
}

export class SecretCipher {
  private keyPromise: Promise<CryptoKey> | null = null

  constructor(
    private readonly keyId: string,
    private readonly keyStore: CryptoKeyStore = new IndexedDbCryptoKeyStore(),
  ) {}

  isEncrypted(value: string) {
    return value.startsWith(ENCRYPTED_PREFIX)
  }

  async encrypt(value: string) {
    const key = await this.getOrCreateKey()
    const iv = crypto.getRandomValues(new Uint8Array(IV_LENGTH))
    const data = await crypto.subtle.encrypt(
      { name: 'AES-GCM', iv },
      key,
      new TextEncoder().encode(value),
    )
    return `${ENCRYPTED_PREFIX}${toBase64(iv)}:${toBase64(new Uint8Array(data))}`
  }

  async decrypt(value: string): Promise<string | null> {
    if (!this.isEncrypted(value)) return null
    const [iv, data] = value.slice(ENCRYPTED_PREFIX.length).split(':')
    if (!iv || !data) return null
    try {
      const key = await this.keyStore.get(this.keyId)
      if (!key) return null
      const decrypted = await crypto.subtle.decrypt(
        { name: 'AES-GCM', iv: fromBase64(iv) },
        key,
        fromBase64(data),
      )
      return new TextDecoder().decode(decrypted)
    } catch {
      return null
    }
  }

  async destroyKey() {
    this.keyPromise = null
    await this.keyStore.delete(this.keyId)
  }

  private getOrCreateKey() {
    if (!this.keyPromise) {
      this.keyPromise = this.loadOrCreateKey().catch((error) => {
        this.keyPromise = null
        throw error
      })
    }
    return this.keyPromise
  }

  private async loadOrCreateKey() {
    const existing = await this.keyStore.get(this.keyId)
    if (existing) return existing
    const key = await crypto.subtle.generateKey({ name: 'AES-GCM', length: 256 }, false, [
      'encrypt',
      'decrypt',
    ])
    await this.keyStore.set(this.keyId, key)
    return key
  }
}
