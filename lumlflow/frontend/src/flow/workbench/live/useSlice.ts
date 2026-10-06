import { computed, getCurrentScope, onScopeDispose, ref, shallowRef, watch } from 'vue'
import type { ComputedRef, Ref } from 'vue'

import type { CellSummary } from '@/flow/api/types'
import type { FlowSessionHandle } from './useFlowSession'

export interface SliceHandle {
  cells: Ref<CellSummary[]>
  transitive: ComputedRef<CellSummary[]>
  direct: ComputedRef<CellSummary[]>
  loading: Ref<boolean>
  error: Ref<string | null>
  refresh: () => Promise<void>
  applyOrder: (slug: string, order: string) => void
}

export function useSlice(
  session: FlowSessionHandle,
  branch: Ref<string | null> | ComputedRef<string | null>,
): SliceHandle {
  const cached = new Map<string, CellSummary[]>()
  const cells = shallowRef<CellSummary[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  let fetched = -1

  async function load(name: string, force: boolean): Promise<void> {
    const held = cached.get(name)
    if (held !== undefined && !force) {
      cells.value = held
      return
    }
    loading.value = true
    try {
      const page = await session.request('cells.list', {
        flow: session.brief.value?.path,
        branch: name,
      })
      cached.set(name, page.cells)
      if (branch.value === name) cells.value = page.cells
      error.value = null
    } catch (failure) {
      error.value = failure instanceof Error ? failure.message : String(failure)
    } finally {
      loading.value = false
    }
  }

  async function refresh(): Promise<void> {
    const name = branch.value
    if (name) await load(name, true)
  }

  function applyOrder(slug: string, order: string): void {
    const name = branch.value
    if (!name) return
    const page = cached.get(name) ?? cells.value
    const updated = page.map((cell) => (cell.slug === slug ? { ...cell, order } : cell))
    cached.clear()
    cached.set(name, updated)
    cells.value = updated
  }

  const stopState = session.onState((frame) => {
    if (frame.state !== 'order_changed' && frame.state !== 'experiment_removed') return
    cached.clear()
    const name = branch.value
    if (name) void load(name, true)
  })
  if (getCurrentScope()) onScopeDispose(stopState)

  watch(
    [branch, session.revision],
    ([name, revision]) => {
      if (!name) {
        cells.value = []
        return
      }
      const moved = revision !== fetched
      if (moved) {
        fetched = revision
        cached.clear()
      }
      void load(name, moved)
    },
    { immediate: true },
  )

  return {
    cells,
    direct: computed(() => cells.value.filter((cell) => cell.state !== 'synced')),
    transitive: computed(() => cells.value.filter((cell) => cell.transitive)),
    loading,
    error,
    refresh,
    applyOrder,
  }
}
