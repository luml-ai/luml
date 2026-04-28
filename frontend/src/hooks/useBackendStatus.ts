import { ref } from 'vue'
import { api } from '@/lib/api'

const EXPECTED_MAJOR = 0

function parseMajor(version: string): number | null {
  const n = parseInt(version.split('.')[0], 10)
  return Number.isNaN(n) ? null : n
}

export function useBackendStatus() {
  const isOffline = ref(false)
  const isLoading = ref(true)
  const versionMismatch = ref(false)

  async function check(): Promise<boolean> {
    isLoading.value = true
    isOffline.value = false
    versionMismatch.value = false

    try {
      const resp = await api.dataAgent.health()

      if (resp.service !== 'luml-prisma') {
        isOffline.value = true
        return false
      }

      const major = parseMajor(resp.version)
      if (major === null || major !== EXPECTED_MAJOR) {
        versionMismatch.value = true
        return false
      }

      return true
    } catch {
      isOffline.value = true
      return false
    } finally {
      isLoading.value = false
    }
  }

  return { isOffline, isLoading, versionMismatch, check }
}
