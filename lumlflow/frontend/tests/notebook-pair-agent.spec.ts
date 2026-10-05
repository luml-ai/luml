/**
 * The notebooks page's pairing line: detected, never declared.
 *
 * "Paired" is read off the daemon's lease state, not off a list the user picks
 * from. The dialog behind the button detects harnesses and offers to set them
 * up; the one thing it can do to a session is end a registration nobody is
 * behind.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ToastService from 'primevue/toastservice'

import type { AgentHarness, AgentSessionRecord } from '@/flow/api/types'
import type { BranchRecord } from '@/api/slices/workspace/workspace.interface'

vi.mock('@/api/slices/workspace/workspace.api', () => ({
  workspaceApi: {
    tree: vi.fn(),
    agentHarnesses: vi.fn(),
    setupAgentHarness: vi.fn(),
    removeAgentHarness: vi.fn(),
    endAgentSession: vi.fn(),
    cellsList: vi.fn(async () => ({ flow: 'churn', branch: 'main', cells: [] })),
    journalSince: vi.fn(async () => ({
      flow: 'churn',
      path: '/p/churn.flow',
      cursor: 0,
      transactions: [],
    })),
  },
}))

// The store takes a toast at creation, outside any component; the component's
// own toast comes from the ToastService plugin below.
const toasts: unknown[] = []
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: (toast: unknown) => toasts.push(toast) }),
}))
vi.mock('primevue/usetoast', () => ({
  useToast: () => ({ add: (toast: unknown) => toasts.push(toast) }),
}))

import { workspaceApi } from '@/api/slices/workspace/workspace.api'
import NotebookPairAgent from '@/components/notebooks/NotebookPairAgent.vue'
import { useFlowStore } from '@/store/flow'
import { settle } from './fakes'

const mocked = workspaceApi as unknown as Record<string, ReturnType<typeof vi.fn>>

const CLAUDE_HARNESS: AgentHarness = {
  id: 'claude-code',
  display_name: 'Claude Code',
  state: 'not set up',
  config_path: '/home/dana/.claude.json',
  snippet: '{"mcpServers":{"lumlflow":{"command":"lumlflow","args":["mcp"]}}}',
  can_setup: true,
  action: 'setup',
  consent_required: true,
  consent_prompt: 'Allow lumlflow to update /home/dana/.claude.json and keep its entry current?',
  post_write_hint: 'approve the server when Claude Code asks',
  shell: true,
  shell_hint: 'also works without setup: run `lumlflow guide` in it',
  error: null,
}

const MAIN: BranchRecord = {
  branch: 'main',
  branch_id: 'branch-main',
  parent: null,
  forked_at_step: 0,
  parent_step: null,
  archived: false,
  checked_out: true,
  cells: 1,
  head_step: 3,
  newest_step: 3,
  last_intent: { ts: '2026-08-13T09:14:00Z', step: 3 },
  agent: 'Codex',
}

const STALE_CODEX: AgentSessionRecord = { actor: 'codex', label: 'Codex', begun_step: 2, leased: false }
const LIVE_CLAUDE: AgentSessionRecord = {
  actor: 'claude-code-1',
  label: 'Claude Code',
  begun_step: 3,
  leased: true,
}

function overlay(): string {
  return document.body.textContent ?? ''
}

function overlayButton(text: string): HTMLButtonElement | undefined {
  return [...document.body.querySelectorAll('button')].find((node) =>
    (node.textContent ?? '').includes(text),
  )
}

async function clickInOverlay(text: string): Promise<void> {
  const found = overlayButton(text)
  expect(found, `no overlay button reading "${text}"`).toBeTruthy()
  found?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
  await settle()
}

function pairingLine(sessions: AgentSessionRecord[]): {
  wrapper: VueWrapper
  store: ReturnType<typeof useFlowStore>
} {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useFlowStore()
  store.branches = [MAIN]
  store.agentSessions = sessions
  const wrapper = mount(NotebookPairAgent, {
    attachTo: document.body,
    global: { plugins: [pinia, ToastService] },
  })
  return { wrapper, store }
}

describe('the notebooks pairing line', () => {
  beforeEach(() => {
    for (const fn of Object.values(mocked)) fn.mockClear?.()
    mocked.agentHarnesses.mockResolvedValue({ harnesses: [CLAUDE_HARNESS] })
    mocked.tree.mockResolvedValue({
      flow: 'churn',
      branch: 'main',
      agent_sessions: [],
      branches: [MAIN],
    })
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('reads a registration without a connection as unpaired, whatever the branch says', () => {
    // `MAIN.agent` names Codex — the newest registration — and that is exactly
    // the row this line must not trust: nobody is behind it.
    const { wrapper } = pairingLine([STALE_CODEX])

    expect(wrapper.text()).toContain('Unpaired')
    expect(wrapper.text()).not.toContain('Codex paired')
    expect(wrapper.text()).toContain('Pair an agent')
    wrapper.unmount()
  })

  it('reads a leased session as paired, by the label the connection registered', () => {
    const { wrapper } = pairingLine([LIVE_CLAUDE, STALE_CODEX])

    expect(wrapper.text()).toContain('Claude Code paired')
    expect(wrapper.text()).toContain('Agents')
    wrapper.unmount()
  })

  it('offers no command to copy and no agent to pick', () => {
    const { wrapper } = pairingLine([])

    expect(wrapper.find('[aria-label="Copy agent connection command"]').exists()).toBe(false)
    expect(wrapper.findAll('button')).toHaveLength(1)
    wrapper.unmount()
  })

  it('detects harnesses whenever the dialog opens, and renders each with its state', async () => {
    const { wrapper } = pairingLine([])

    await wrapper.get('.toolbar-pair-button').trigger('click')
    await settle()

    expect(mocked.agentHarnesses).toHaveBeenCalledTimes(1)
    expect(overlay()).toContain('Claude Code')
    expect(overlay()).toContain('not set up')
    expect(overlay()).toContain('paired when it connects over MCP')
    wrapper.unmount()
  })

  it('sets a harness up through the daemon after consent, and shows the result', async () => {
    mocked.setupAgentHarness.mockResolvedValue({
      ...CLAUDE_HARNESS,
      state: 'set up',
      action: null,
      consent_required: false,
      consent_prompt: null,
    })
    const { wrapper } = pairingLine([])

    await wrapper.get('.toolbar-pair-button').trigger('click')
    await settle()
    const checkbox = document.body.querySelector<HTMLInputElement>('input[type="checkbox"]')
    expect(checkbox, 'no harness to select').toBeTruthy()
    checkbox?.click()
    await settle()
    await clickInOverlay('Set up')
    await clickInOverlay('Allow and set up')

    expect(mocked.setupAgentHarness).toHaveBeenCalledWith('claude-code', true)
    expect(overlay()).toContain('set up')
    expect(overlay()).toContain('approve the server when Claude Code asks')
    wrapper.unmount()
  })

  it('removes a set-up harness through the daemon', async () => {
    const configured: AgentHarness = {
      ...CLAUDE_HARNESS,
      state: 'set up',
      action: null,
      consent_required: false,
      consent_prompt: null,
    }
    mocked.agentHarnesses.mockResolvedValue({ harnesses: [configured] })
    mocked.removeAgentHarness.mockResolvedValue({ ...CLAUDE_HARNESS, state: 'removed by you' })
    const { wrapper } = pairingLine([])

    await wrapper.get('.toolbar-pair-button').trigger('click')
    await settle()
    await clickInOverlay('Remove')

    expect(mocked.removeAgentHarness).toHaveBeenCalledWith('claude-code')
    expect(overlay()).toContain('removed by you')
    wrapper.unmount()
  })

  it('lists registered sessions, and ends only one nobody is connected through', async () => {
    mocked.endAgentSession.mockResolvedValue({ flow: '/p/churn.flow', actor: 'codex', label: 'Codex' })
    const { wrapper } = pairingLine([LIVE_CLAUDE, STALE_CODEX])

    await wrapper.get('.toolbar-pair-button').trigger('click')
    await settle()

    const rows = [...document.body.querySelectorAll<HTMLElement>('[data-actor]')]
    expect(rows.map((row) => row.dataset.actor)).toEqual(['claude-code-1', 'codex'])
    expect(rows[0]?.textContent).toContain('connected')
    expect(rows[0]?.querySelector('button')).toBeNull()
    expect(rows[1]?.textContent).toContain('registered, no connection')

    await clickInOverlay('End')

    expect(mocked.endAgentSession).toHaveBeenCalledWith('codex', undefined)
    // The store re-reads the tree once the end is committed.
    expect(mocked.tree).toHaveBeenCalled()
    wrapper.unmount()
  })
})
