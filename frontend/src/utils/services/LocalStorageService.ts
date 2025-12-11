import type { LocalStorageProviderSettings } from './LocalStorageService.interfaces'

type StorageValueMap = {
  providersSettings: LocalStorageProviderSettings
  currentOrganizationId: string
}

type StorageKey = keyof StorageValueMap

class LocalStorageServiceClass {
  get<K extends StorageKey>(key: K): StorageValueMap[K] | null {
    const raw = localStorage.getItem(key)
    if (raw === null) return null
    try {
      return JSON.parse(raw) as StorageValueMap[K]
    } catch {
      return null
    }
  }

  set<K extends StorageKey>(key: K, value: StorageValueMap[K]): void {
    localStorage.setItem(key, JSON.stringify(value))
  }

  remove<K extends StorageKey>(key: K): void {
    localStorage.removeItem(key)
  }

  clear(): void {
    localStorage.clear()
  }
}

export const LocalStorageService = new LocalStorageServiceClass()
