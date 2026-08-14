import { ref, type Ref } from 'vue'

/** How long the button says it copied before going back to offering to. */
const ACKNOWLEDGED_MS = 1500

/**
 * The clipboard, and the acknowledgement that it took. Shared by the one-line
 * field and the block so the two cannot drift on the timing or on what happens
 * when the clipboard is unavailable — an insecure context has none, and both
 * fall back to the selection the reader can make by hand.
 */
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
      // No clipboard here; `select-all` is what is left, and it still works.
    }
  }

  return { copied, copy }
}
