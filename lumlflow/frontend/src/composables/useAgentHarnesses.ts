import { computed, ref } from 'vue'
import type { AgentHarness } from '@/flow/api/types'

export interface HarnessRpc {
  list: () => Promise<{ harnesses: AgentHarness[] }>
  setup: (id: string, consent: boolean) => Promise<AgentHarness>
  remove: (id: string) => Promise<AgentHarness>
}

export function useAgentHarnesses(rpc: HarnessRpc, onError: (failure: unknown) => void) {
  const harnesses = ref<AgentHarness[]>([])
  const loading = ref(false)
  const loadError = ref<string | null>(null)
  const busy = ref<Set<string>>(new Set())
  const busyIds = computed(() => [...busy.value])
  // Detection is re-run whenever the section opens; only the newest read may
  // land, or a slow first answer would overwrite a fresh second one.
  let read = 0

  async function refresh(): Promise<void> {
    const mine = ++read
    loading.value = true
    loadError.value = null
    try {
      const answer = await rpc.list()
      if (mine === read) harnesses.value = answer.harnesses
    } catch (failure) {
      if (mine === read) {
        loadError.value = failure instanceof Error ? failure.message : String(failure)
      }
    } finally {
      if (mine === read) loading.value = false
    }
  }

  function setBusy(id: string, on: boolean): void {
    const next = new Set(busy.value)
    if (on) next.add(id)
    else next.delete(id)
    busy.value = next
  }

  function apply(next: AgentHarness): void {
    const at = harnesses.value.findIndex((harness) => harness.id === next.id)
    if (at < 0) {
      harnesses.value = [...harnesses.value, next]
      return
    }
    harnesses.value = harnesses.value.map((harness, index) => (index === at ? next : harness))
  }

  async function setupOne(id: string, consent: boolean): Promise<void> {
    setBusy(id, true)
    try {
      apply(await rpc.setup(id, consent))
    } catch (failure) {
      onError(failure)
    } finally {
      setBusy(id, false)
    }
  }

  async function setup(ids: string[], consent: boolean): Promise<void> {
    for (const id of ids) await setupOne(id, consent)
  }

  function update(id: string): void {
    void setupOne(id, false)
  }

  async function remove(id: string): Promise<void> {
    setBusy(id, true)
    try {
      apply(await rpc.remove(id))
    } catch (failure) {
      onError(failure)
    } finally {
      setBusy(id, false)
    }
  }

  return { harnesses, loading, loadError, busyIds, refresh, setup, update, remove }
}
