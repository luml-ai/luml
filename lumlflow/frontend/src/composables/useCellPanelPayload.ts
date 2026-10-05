import type { CellSummary } from '@/api/slices/workspace/workspace.interface'
import { onBeforeMount, ref, watch, type Ref } from 'vue'
import { useFlowStore } from '@/store/flow'

interface CellPanelPayloadOptions<T> {
  slug: () => string
  /** The part of the cell summary whose change makes the payload out of date. */
  follows: (cell: CellSummary) => unknown
  fetch: () => Promise<T>
  onLoaded: (payload: T) => void
  onFailed: (error: unknown) => void
}

/**
 * Loads a notebook panel's payload when it mounts, and again whenever the lane
 * on screen or the followed part of the cell changes. Only the latest load
 * lands: a response a later reload superseded is dropped, error or not.
 */
export function useCellPanelPayload<T>(options: CellPanelPayloadOptions<T>): {
  isLoading: Ref<boolean>
  reload: () => Promise<void>
} {
  const flowStore = useFlowStore()
  const isLoading = ref(true)
  let latest = 0

  async function reload(): Promise<void> {
    const mine = ++latest
    try {
      const payload = await options.fetch()
      if (mine === latest) options.onLoaded(payload)
    } catch (error) {
      if (mine === latest) options.onFailed(error)
    } finally {
      if (mine === latest) isLoading.value = false
    }
  }

  onBeforeMount(reload)
  watch(
    [
      () => flowStore.currentBranch?.branch,
      () => {
        const cell = flowStore.cells.find((entry) => entry.slug === options.slug())
        return cell ? options.follows(cell) : undefined
      },
    ],
    reload,
  )

  return { isLoading, reload }
}
