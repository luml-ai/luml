import { ref, type Ref } from 'vue'

const ACKNOWLEDGED_MS = 1500

export function useCopy(value: () => string): { copied: Ref<boolean>; copy: () => Promise<void> } {
  const copied = ref(false)

  async function copy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(value())
      copied.value = true
      setTimeout(() => {
        copied.value = false
      }, ACKNOWLEDGED_MS)
    } catch {
    }
  }

  return { copied, copy }
}
