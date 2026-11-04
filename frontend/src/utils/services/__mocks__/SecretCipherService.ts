import { vi } from 'vitest'
import type { CryptoKeyStore } from '../SecretCipherService'

const { SecretCipher: ActualSecretCipher } =
  await vi.importActual<typeof import('../SecretCipherService')>('../SecretCipherService')

export const memoryKeyStore = new Map<string, CryptoKey>()

const keyStore: CryptoKeyStore = {
  get: async (id) => memoryKeyStore.get(id),
  set: async (id, key) => {
    memoryKeyStore.set(id, key)
  },
  delete: async (id) => {
    memoryKeyStore.delete(id)
  },
}

export class SecretCipher extends ActualSecretCipher {
  constructor(keyId: string) {
    super(keyId, keyStore)
  }
}
