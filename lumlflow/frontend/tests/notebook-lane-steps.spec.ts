
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ToastService from 'primevue/toastservice'
import Tooltip from 'primevue/tooltip'

import type { BranchRecord, JournalTransaction } from '@/api/slices/workspace/workspace.interface'

vi.mock('@/api/slices/workspace/workspace.api', () => ({
  workspaceApi: {
    rewindBranch: vi.fn(async () => ({})),
    checkpointBranch: vi.fn(async () => ({})),
    tree: vi.fn(async () => ({ flow: 'churn', branches: [], agent_sessions: [] })),
    cellsList: vi.fn(async () => ({ cells: [] })),
    journalSince: vi.fn(async () => ({ transactions: [] })),
  },
}))
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: () => {} }),
}))
vi.mock('primevue/usetoast', () => ({ useToast: () => ({ add: () => {} }) }))

import { workspaceApi } from '@/api/slices/workspace/workspace.api'
import NotebookLanesSteps from '@/components/notebooks/lanes/NotebookLanesSteps.vue'
import { useFlowStore } from '@/store/flow'
import { settle } from './fakes'

const mocked = workspaceApi as unknown as Record<string, ReturnType<typeof vi.fn>>

const MAIN = {
  branch: 'main',
  branch_id: 'b-main',
  checked_out: true,
  head_step: 91,
  newest_step: 91,
  parent: null,
  parent_step: null,
} as unknown as BranchRecord

function step(
  at: number,
  intent: string,
  ops: Record<string, unknown>[] = [{ op: 'cell_accepted' }],
): JournalTransaction {
  return {
    step: at,
    ts: new Date().toISOString(),
    actor: 'user',
    intent,
    offline: false,
    settled: false,
    branch: 'b-main',
    ops,
  } as unknown as JournalTransaction
}

let store: ReturnType<typeof useFlowStore>
let wrapper: VueWrapper

function rows(): HTMLElement[] {
  return [...(wrapper.element as HTMLElement).querySelectorAll<HTMLElement>('.step')]
}

beforeEach(async () => {
  for (const fn of Object.values(mocked)) fn.mockClear()
  setActivePinia(createPinia())
  store = useFlowStore()
  store.branches = [MAIN]
  store.journal = [
    step(86, 'reused a cached train_model'),
    step(90, 'added split_copy'),
    step(91, 'ran split_copy'),
    step(92, 'Important point!!!', [{ op: 'checkpointed', step: 90 }]),
  ]
  wrapper = mount(NotebookLanesSteps, {
    attachTo: document.body,
    global: { plugins: [PrimeVue, ToastService], directives: { tooltip: Tooltip } },
  })
  await wrapper.find('.p-accordionheader').trigger('click')
  await settle()
})

afterEach(() => wrapper.unmount())

describe('the steps list', () => {
  it('highlights the step the lane stands on, and has no go buttons', () => {
    const current = rows().filter((row) => row.classList.contains('step--current'))
    expect(current.map((row) => row.dataset.step)).toEqual(['91'])
    expect(wrapper.text()).not.toContain('Go')
    expect(wrapper.text()).not.toContain('Mark as Point')
  })

  it('moves the lane to a step when its row is clicked, and not to where it is', async () => {
    rows()
      .find((row) => row.dataset.step === '86')
      ?.click()
    await settle()
    expect(mocked.rewindBranch).toHaveBeenCalledWith('main', 86, undefined)

    mocked.rewindBranch.mockClear()
    rows()
      .find((row) => row.dataset.step === '91')
      ?.click()
    await settle()
    expect(mocked.rewindBranch).not.toHaveBeenCalled()
  })

  it('shows a point with its flag, and offers the flag on every other step', () => {
    const point = rows().find((row) => row.dataset.step === '90')
    expect(point?.textContent).toContain('Important point!!!')
    expect(point?.textContent).toContain('added split_copy')
    expect(point?.querySelector('[aria-label="Mark as point"]')).toBeNull()
    expect(
      rows()
        .filter((row) => row.dataset.step !== '90')
        .every((row) => row.querySelector('[aria-label="Mark as point"]')),
    ).toBe(true)
  })

  it('marks the step whose flag was used, without moving the lane', async () => {
    const older = rows().find((row) => row.dataset.step === '86')
    older?.querySelector<HTMLButtonElement>('[aria-label="Mark as point"]')?.click()
    await settle()
    expect(mocked.rewindBranch).not.toHaveBeenCalled()

    const input = document.body.querySelector<HTMLInputElement>('#point-name')
    expect(input).not.toBeNull()
    input!.value = 'baseline'
    input!.dispatchEvent(new Event('input'))
    await settle()
    document.body.querySelector<HTMLFormElement>('.form')?.requestSubmit()
    await settle()
    await settle()
    expect(mocked.checkpointBranch).toHaveBeenCalledWith('main', 'baseline', undefined, 86)
  })
})
