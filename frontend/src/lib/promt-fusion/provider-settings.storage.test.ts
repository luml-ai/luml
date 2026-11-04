import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LocalStorageService } from '@/utils/services/LocalStorageService'
import { ProvidersEnum, type ProviderSetting } from './prompt-fusion.interfaces'
import {
  getNonSecretProviderSettings,
  loadSavedProviderSettings,
  providerSecretsCipher,
  saveProviderSettings,
  setApiKeysStorageEnabled,
} from './provider-settings.storage'

vi.mock('@/utils/services/SecretCipherService')

const apiKeySetting = (value: string): ProviderSetting[] => [
  { id: 'apiKey', label: 'API Key', placeholder: '', required: true, value },
]

function storedOpenAiKey() {
  return LocalStorageService.get('providersSettings')?.openAi?.apiKey
}

describe('provider settings storage', () => {
  beforeEach(async () => {
    localStorage.clear()
    await providerSecretsCipher.destroyKey()
  })

  it('stores API keys encrypted and loads them back', async () => {
    await setApiKeysStorageEnabled(true)
    await saveProviderSettings(ProvidersEnum.openAi, apiKeySetting('sk-test-secret'))

    expect(storedOpenAiKey()).toMatch(/^enc:v1:/)
    expect(localStorage.getItem('providersSettings')).not.toContain('sk-test-secret')
    expect(await loadSavedProviderSettings()).toEqual({
      openAi: { apiKey: 'sk-test-secret' },
    })
  })

  it('does not store anything while storage is disabled', async () => {
    await setApiKeysStorageEnabled(false)
    await saveProviderSettings(ProvidersEnum.openAi, apiKeySetting('sk-test-secret'))

    expect(storedOpenAiKey()).toBeUndefined()
  })

  it('keeps non-secret settings in plain text', async () => {
    await setApiKeysStorageEnabled(true)
    await saveProviderSettings(ProvidersEnum.ollama, [
      { id: 'apiBase', label: 'API Base', placeholder: '', required: true, value: 'http://x:1' },
    ])

    expect(LocalStorageService.get('providersSettings')?.ollama).toEqual({ apiBase: 'http://x:1' })
  })

  it('encrypts legacy plaintext keys on load', async () => {
    LocalStorageService.set('providersSettings', {
      saveApiKeys: true,
      openAi: { apiKey: 'sk-legacy' },
    })

    expect(await loadSavedProviderSettings()).toEqual({ openAi: { apiKey: 'sk-legacy' } })
    expect(storedOpenAiKey()).toMatch(/^enc:v1:/)
    expect(await loadSavedProviderSettings()).toEqual({ openAi: { apiKey: 'sk-legacy' } })
  })

  it('drops stored keys and ignores them when storage is disabled', async () => {
    LocalStorageService.set('providersSettings', {
      saveApiKeys: false,
      openAi: { apiKey: 'sk-legacy' },
      ollama: { apiBase: 'http://x:1' },
    })

    expect(await loadSavedProviderSettings()).toEqual({
      openAi: {},
      ollama: { apiBase: 'http://x:1' },
    })
    expect(storedOpenAiKey()).toBeUndefined()
  })

  it('drops keys that can no longer be decrypted', async () => {
    await setApiKeysStorageEnabled(true)
    await saveProviderSettings(ProvidersEnum.openAi, apiKeySetting('sk-test-secret'))
    await providerSecretsCipher.destroyKey()

    expect(await loadSavedProviderSettings()).toEqual({ openAi: {} })
    expect(storedOpenAiKey()).toBeUndefined()
  })

  it('destroys the key and stored ciphertext on opt-out', async () => {
    await setApiKeysStorageEnabled(true)
    await saveProviderSettings(ProvidersEnum.openAi, apiKeySetting('sk-test-secret'))
    const encrypted = storedOpenAiKey() as string

    await setApiKeysStorageEnabled(false)

    expect(storedOpenAiKey()).toBeUndefined()
    expect(await providerSecretsCipher.decrypt(encrypted)).toBeNull()
  })

  it('never exposes secrets through the synchronous reader', async () => {
    await setApiKeysStorageEnabled(true)
    await saveProviderSettings(ProvidersEnum.openAi, apiKeySetting('sk-test-secret'))

    expect(getNonSecretProviderSettings()).toEqual({ openAi: {} })
  })
})
