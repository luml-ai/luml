import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { computed, ref } from 'vue'
import type { ExperimentSnapshotProvider } from '@/interfaces/interfaces'
import { useEvalsStore } from '@/store/evals'
import { INITIAL_REQUEST_PARAMS } from '@/store/trace/trace.data'
import { useTracesTable } from '../useTracesTable'
import { useEvalsTable } from '../useEvalsTable'

const downloads = vi.hoisted(() => [] as Blob[])

vi.mock('primevue', () => ({ useToast: () => ({ add: vi.fn() }) }))
vi.mock('@/helpers/files', () => ({
  downloadFileFromBlob: (blob: Blob) => downloads.push(blob),
}))

const annotations = {
  feedback: [{ name: 'correct', total: 3, counts: { true: 2, false: 1 } }],
  expectations: [{ name: 'answer', total: 1, positive: 1, negative: 0, value: 'Paris' }],
}

const exportedColumns = ['correct (feedback)', 'answer (expectation)']

function setupProvider() {
  const provider = {
    getAllTraces: vi.fn(async () => [
      { trace_id: 't1', created_at: '2026-01-01T00:00:00Z', annotations },
    ]),
    getAllDatasetEvals: vi.fn(async () => [{ id: 'e1', dataset_id: 'd1', annotations }]),
  }
  useEvalsStore().setProvider(provider as unknown as ExperimentSnapshotProvider)
}

async function downloadedCsv() {
  expect(downloads).toHaveLength(1)
  const text = await new Promise<string>((resolve) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.readAsText(downloads[0]!)
  })
  return text.trim().split('\n')
}

describe('CSV export of annotation columns', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    downloads.length = 0
    setupProvider()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  const expectedCsv = ['correct (feedback),answer (expectation)', '"2 positive, 1 negative",Paris']

  it('writes the feedback counts and the expected value of a trace', async () => {
    const { exportCSV } = useTracesTable(
      ref([]),
      ref(exportedColumns),
      ref({ ...INITIAL_REQUEST_PARAMS }),
    )
    await exportCSV()

    expect(await downloadedCsv()).toEqual(expectedCsv)
  })

  it('writes the feedback counts and the expected value of an eval', async () => {
    const { exportCSV } = useEvalsTable(
      computed(() => []),
      ref(''),
      'd1',
      ref(exportedColumns),
      ref([]),
    )
    await exportCSV()

    expect(await downloadedCsv()).toEqual(expectedCsv)
  })
})
