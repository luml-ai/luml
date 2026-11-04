import { describe, expect, it } from 'vitest'
import { SecretCipher, type CryptoKeyStore } from './SecretCipherService'

function createKeyStore() {
  const keys = new Map<string, CryptoKey>()
  const store: CryptoKeyStore = {
    get: async (id) => keys.get(id),
    set: async (id, key) => {
      keys.set(id, key)
    },
    delete: async (id) => {
      keys.delete(id)
    },
  }
  return { keys, store }
}

describe('SecretCipher', () => {
  it('round-trips values without exposing plaintext or key material', async () => {
    const { keys, store } = createKeyStore()
    const cipher = new SecretCipher('test', store)

    const encrypted = await cipher.encrypt('sk-test-secret')

    expect(cipher.isEncrypted(encrypted)).toBe(true)
    expect(encrypted).not.toContain('sk-test-secret')
    expect(await cipher.encrypt('sk-test-secret')).not.toBe(encrypted)
    expect(await cipher.decrypt(encrypted)).toBe('sk-test-secret')
    expect(keys.get('test')?.extractable).toBe(false)
  })

  it('reuses the persisted key across instances', async () => {
    const { store } = createKeyStore()
    const encrypted = await new SecretCipher('test', store).encrypt('sk-test-secret')

    expect(await new SecretCipher('test', store).decrypt(encrypted)).toBe('sk-test-secret')
  })

  it('cannot decrypt after the key is destroyed', async () => {
    const { store } = createKeyStore()
    const cipher = new SecretCipher('test', store)
    const encrypted = await cipher.encrypt('sk-test-secret')

    await cipher.destroyKey()

    expect(await cipher.decrypt(encrypted)).toBeNull()
    const reencrypted = await cipher.encrypt('sk-test-secret')
    expect(await cipher.decrypt(reencrypted)).toBe('sk-test-secret')
  })

  it.each(['sk-plaintext', 'enc:v1:broken', 'enc:v1:AAAA:AAAA'])(
    'returns null for non-decryptable value %s',
    async (value) => {
      const { store } = createKeyStore()
      const cipher = new SecretCipher('test', store)
      await cipher.encrypt('warm-up')

      expect(await cipher.decrypt(value)).toBeNull()
    },
  )
})
