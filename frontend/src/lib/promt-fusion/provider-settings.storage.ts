import type { LocalStorageProviderSettings } from '@/utils/services/LocalStorageService.interfaces'
import { LocalStorageService } from '@/utils/services/LocalStorageService'
import { SecretCipher } from '@/utils/services/SecretCipherService'
import { ProvidersEnum, type ProviderSetting } from './prompt-fusion.interfaces'

export type SavedProviderSettings = Partial<Record<ProvidersEnum, Record<string, string>>>

const SECRET_SETTING_IDS = ['apiKey']

export const providerSecretsCipher = new SecretCipher('providers-settings')

function isSecret(settingId: string) {
  return SECRET_SETTING_IDS.includes(settingId)
}

function removeSecrets(settings: LocalStorageProviderSettings) {
  for (const providerId of Object.values(ProvidersEnum)) {
    const provider = settings[providerId]
    if (!provider) continue
    settings[providerId] = Object.fromEntries(
      Object.entries(provider).filter(([id]) => !isSecret(id)),
    )
  }
}

async function encryptSettings(values: Record<string, string>) {
  const entries = await Promise.all(
    Object.entries(values).map(async ([id, value]) => [
      id,
      isSecret(id) && value ? await providerSecretsCipher.encrypt(value) : value,
    ]),
  )
  return Object.fromEntries(entries) as Record<string, string>
}

async function writeEncrypted(saved: SavedProviderSettings) {
  const encrypted = await Promise.all(
    Object.entries(saved).map(
      async ([providerId, values]) => [providerId, await encryptSettings(values)] as const,
    ),
  )
  const stored = LocalStorageService.get('providersSettings')
  if (!stored?.saveApiKeys) return
  for (const [providerId, values] of encrypted) {
    stored[providerId as ProvidersEnum] = values
  }
  LocalStorageService.set('providersSettings', stored)
}

export function isApiKeysStorageEnabled() {
  return !!LocalStorageService.get('providersSettings')?.saveApiKeys
}

export async function setApiKeysStorageEnabled(enabled: boolean) {
  const settings = LocalStorageService.get('providersSettings') || {}
  settings.saveApiKeys = enabled
  if (!enabled) removeSecrets(settings)
  LocalStorageService.set('providersSettings', settings)
  if (enabled) return
  try {
    await providerSecretsCipher.destroyKey()
  } catch (error) {
    console.warn('Failed to remove provider secrets key', error)
  }
}

export function getNonSecretProviderSettings(): SavedProviderSettings {
  const stored = LocalStorageService.get('providersSettings')
  const result: SavedProviderSettings = {}
  for (const providerId of Object.values(ProvidersEnum)) {
    const values = stored?.[providerId]
    if (!values) continue
    result[providerId] = Object.fromEntries(Object.entries(values).filter(([id]) => !isSecret(id)))
  }
  return result
}

export async function loadSavedProviderSettings(): Promise<SavedProviderSettings> {
  const stored = LocalStorageService.get('providersSettings')
  const result = getNonSecretProviderSettings()
  if (!stored) return result
  let needsRewrite = false
  for (const providerId of Object.values(ProvidersEnum)) {
    const values = stored[providerId]
    if (!values) continue
    for (const [id, value] of Object.entries(values)) {
      if (!isSecret(id)) continue
      if (!stored.saveApiKeys || !providerSecretsCipher.isEncrypted(value)) needsRewrite = true
      if (!stored.saveApiKeys) continue
      const plain = providerSecretsCipher.isEncrypted(value)
        ? await providerSecretsCipher.decrypt(value)
        : value
      if (plain === null) {
        needsRewrite = true
        continue
      }
      result[providerId] = { ...result[providerId], [id]: plain }
    }
  }
  if (!needsRewrite) return result
  if (!stored.saveApiKeys) {
    removeSecrets(stored)
    LocalStorageService.set('providersSettings', stored)
    return result
  }
  try {
    await writeEncrypted(result)
  } catch (error) {
    console.warn('Failed to encrypt saved provider settings', error)
    const current = LocalStorageService.get('providersSettings')
    if (current) {
      removeSecrets(current)
      LocalStorageService.set('providersSettings', current)
    }
  }
  return result
}

export async function saveProviderSettings(providerId: ProvidersEnum, settings: ProviderSetting[]) {
  if (!isApiKeysStorageEnabled()) return
  const values = Object.fromEntries(settings.map((setting) => [setting.id, setting.value]))
  try {
    await writeEncrypted({ [providerId]: values })
  } catch (error) {
    console.warn('Failed to save provider settings', error)
  }
}
