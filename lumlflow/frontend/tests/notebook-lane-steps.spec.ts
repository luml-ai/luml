
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
const confirmRequire = vi.hoisted(() => vi.fn())
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: () => {} }),
  useConfirm: () => ({ require: confirmRequire }),
}))
vi.mock('primevue/usetoast', () => ({ useToast: () => ({ add: () => {} }) }))

import { workspaceApi } from '@/api/slices/workspace/workspace.api'
import NotebookLanesSteps from '@/components/notebooks/lanes/NotebookLanesSteps.vue'
import type { ConfirmationOptions } from 'primevue/confirmationoptions'
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

function row(at: string): HTMLElement | undefined {
  return rows().find((element) => element.dataset.step === at)
}

function backToLatest(): HTMLButtonElement | undefined {
  return [...(wrapper.element as HTMLElement).querySelectorAll<HTMLButtonElement>('button')].find(
    (button) => button.textContent?.includes('Back to latest'),
  )
}

beforeEach(async () => {
  for (const fn of Object.values(mocked)) fn.mockClear()
  confirmRequire.mockClear()
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

  it('asks to confirm a move that names the clicked step, without moving the lane yet', async () => {
    row('86')?.click()
    await settle()
    expect(mocked.rewindBranch).not.toHaveBeenCalled()
    expect(confirmRequire).toHaveBeenCalledOnce()
    const options = confirmRequire.mock.calls[0]![0] as ConfirmationOptions
    expect(options.header).toContain('step 86')
    expect(options.message).toContain('step 86')

    confirmRequire.mockClear()
    row('91')?.click()
    await settle()
    expect(confirmRequire).not.toHaveBeenCalled()
  })

  it('moves the lane once the move is confirmed', async () => {
    row('86')?.click()
    await settle()
    const options = confirmRequire.mock.calls[0]![0] as ConfirmationOptions
    options.accept?.()
    await settle()
    expect(mocked.rewindBranch).toHaveBeenCalledOnce()
    expect(mocked.rewindBranch).toHaveBeenCalledWith('main', 86, undefined)
  })

  it('does not move a lane that is no longer checked out when the move is confirmed', async () => {
    row('86')?.click()
    await settle()
    const options = confirmRequire.mock.calls[0]![0] as ConfirmationOptions
    store.branches = [
      { ...MAIN, checked_out: false },
      { ...MAIN, branch: 'other', branch_id: 'b-other', checked_out: true },
    ]
    options.accept?.()
    await settle()
    expect(mocked.rewindBranch).not.toHaveBeenCalled()
  })

  it('does not promise a way back when the confirmed step is the latest one', async () => {
    store.branches = [{ ...MAIN, head_step: 86 }]
    await settle()

    row('90')?.click()
    await settle()
    const older = confirmRequire.mock.calls[0]![0] as ConfirmationOptions
    expect(older.message).toContain('Lane main will move to step 90')
    expect(older.message).toContain('return to its latest step')

    row('91')?.click()
    await settle()
    const latest = confirmRequire.mock.calls[1]![0] as ConfirmationOptions
    expect(latest.message).toBe('Lane main will move to its latest step 91.')
  })

  it('says when the lane is behind its latest step, and offers the way back', async () => {
    store.branches = [{ ...MAIN, head_step: 86 }]
    await settle()
    expect(wrapper.text()).toContain('on step 86')
    expect(wrapper.text()).toContain('not its latest step 91')

    backToLatest()?.click()
    await settle()
    expect(mocked.rewindBranch).toHaveBeenCalledWith('main', 91, undefined)
  })

  it('shows no behind notice when the lane is at its latest step', () => {
    expect(backToLatest()).toBeUndefined()
    expect(wrapper.text()).not.toContain('latest step')
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
