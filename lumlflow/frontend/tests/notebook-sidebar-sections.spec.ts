import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { CellSummary } from '@/api/slices/workspace/workspace.interface'

vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: () => undefined }),
}))

import { useFlowStore } from '@/store/flow'
import { useSidebarSections } from '@/components/notebooks/sidebar-accordion/useSidebarSections'

function cell(slug: string, primary: string, kinds: Record<string, string>): CellSummary {
  return {
    slug,
    state: 'synced',
    primary,
    kinds,
    consumes: {},
    cost_seconds: null,
    causes: [],
    reused: false,
    changed_step: 1,
    order: slug,
    mat_id: null,
  } as CellSummary
}

describe('sidebar sections', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('counts a cell under every kind it produces, not only its primary one', () => {
    const flowStore = useFlowStore()
    flowStore.cells = [
      cell('train', 'run', { run: 'experiment', model: 'model', metrics: 'metric' }),
      cell('fit', 'model', { model: 'model' }),
      cell('evaluate', 'run', { run: 'experiment' }),
      cell('load', 'rows', { rows: 'dataset' }),
    ]

    const counts = Object.fromEntries(
      useSidebarSections().value.map((section) => [section.value, section.count]),
    )

    expect(counts).toMatchObject({ cells: 4, experiments: 2, models: 2 })
  })
})
