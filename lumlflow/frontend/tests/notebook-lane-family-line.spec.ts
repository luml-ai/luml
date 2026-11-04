import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { BranchRecord, JournalTransaction } from '@/api/slices/workspace/workspace.interface'

vi.mock('@/api/slices/workspace/workspace.api', () => ({
  workspaceApi: {
    journalSince: vi.fn(async () => ({ transactions: [] })),
  },
}))
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: () => {} }),
}))
vi.mock('primevue/usetoast', () => ({ useToast: () => ({ add: () => {} }) }))

import { workspaceApi } from '@/api/slices/workspace/workspace.api'
import { useFlowStore } from '@/store/flow'

const mocked = workspaceApi as unknown as Record<string, ReturnType<typeof vi.fn>>

const EXP = {
  branch: 'exp',
  branch_id: 'b-exp',
  checked_out: true,
  head_step: 40,
  newest_step: 40,
  parent: 'main',
  parent_step: 25,
} as unknown as BranchRecord

function on(branch: string, at: number, ops = [{ op: 'cell_accepted' }]): JournalTransaction {
  return {
    step: at,
    ts: new Date().toISOString(),
    actor: 'user',
    intent: `step ${at}`,
    offline: false,
    settled: false,
    branch,
    ops,
  } as unknown as JournalTransaction
}

let store: ReturnType<typeof useFlowStore>

beforeEach(async () => {
  setActivePinia(createPinia())
  store = useFlowStore()
  store.branches = [EXP]
  // Lane `exp` forked at 25. Between its own steps the journal holds another
  // lane's steps and entries that are no steps at all.
  mocked.journalSince!.mockResolvedValueOnce({
    transactions: [
      on('b-exp', 27),
      on('b-main', 28),
      on('b-main', 29),
      on('b-exp', 30),
      on('b-exp', 31, [{ op: 'cells_ordered' }]),
      on('b-exp', 32, [{ op: 'checkpointed' }]),
      on('b-other', 35),
      on('b-exp', 40),
    ],
  })
  await store.fetchJournal()
})

describe('the line under a forked lane', () => {
  it("counts the lane's own steps, not the journal steps since the fork", () => {
    expect(store.currentBranchFamilyLine).toBe('started from main · 3 steps ago')
  })

  it('counts only up to the step the lane stands on', () => {
    store.branches = [{ ...EXP, head_step: 30 }]
    expect(store.currentBranchFamilyLine).toBe('started from main · 2 steps ago')
  })

  it('says one step in the singular', () => {
    store.branches = [{ ...EXP, head_step: 27 }]
    expect(store.currentBranchFamilyLine).toBe('started from main · 1 step ago')
  })
})
