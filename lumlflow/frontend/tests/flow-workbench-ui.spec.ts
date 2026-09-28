import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, nextTick } from 'vue'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import ToastService from 'primevue/toastservice'

import { TOKEN_STORAGE_KEY } from '@/flow/api/token'
import type { AgentHarness } from '@/flow/api/types'
import CellCard from '@/flow/workbench/components/card/CellCard.vue'
import CellOpRow from '@/flow/workbench/components/card/CellOpRow.vue'
import CodeView from '@/flow/workbench/components/card/CodeView.vue'
import AgentsPanel from '@/flow/workbench/components/panel/AgentsPanel.vue'
import LeftPanel from '@/flow/workbench/components/panel/LeftPanel.vue'
import {
  branches,
  cellsByBranch,
  env,
  flaggedCell,
  journal,
  noteCell,
  placeholderCell,
  session,
  settings,
  trainModel,
} from '@/flow/workbench/fixtures'
import type { FlowCell } from '@/flow/workbench/model/types'
import DesignSystemPage from '@/flow/workbench/gallery/DesignSystemPage.vue'
import GallerySpecimen from '@/flow/workbench/gallery/GallerySpecimen.vue'
import BranchGraphSection from '@/flow/workbench/gallery/sections/BranchGraphSection.vue'
import CellCardSection from '@/flow/workbench/gallery/sections/CellCardSection.vue'
import CompareSection from '@/flow/workbench/gallery/sections/CompareSection.vue'
import ErrorsSection from '@/flow/workbench/gallery/sections/ErrorsSection.vue'
import FoundationsSection from '@/flow/workbench/gallery/sections/FoundationsSection.vue'
import LeftPanelSection from '@/flow/workbench/gallery/sections/LeftPanelSection.vue'
import PagesSection from '@/flow/workbench/gallery/sections/PagesSection.vue'
import RenderersSection from '@/flow/workbench/gallery/sections/RenderersSection.vue'
import RunControlsSection from '@/flow/workbench/gallery/sections/RunControlsSection.vue'
import SessionSection from '@/flow/workbench/gallery/sections/SessionSection.vue'
import ComparePage from '@/flow/workbench/pages/ComparePage.vue'
import WorkbenchPage from '@/flow/workbench/pages/WorkbenchPage.vue'
import FlowShell from '@/flow/FlowShell.vue'
import { FakeSocket, fakeDaemon, flowStatus, settle } from './fakes'

/** The flow document every workbench route in this suite is addressed by. */
const FLOW = 'churn.flow'

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

function agentHarness(overrides: Partial<AgentHarness>): AgentHarness {
  return { ...CLAUDE_HARNESS, ...overrides }
}

/**
 * A flow lives inside somebody's git repository, so no word this product puts
 * on screen may be one of git's — a reader should never have to work out which
 * system a sentence is about. `variant` is banned on the same tier from the
 * other side: PrimeVue and the Experiments half of this product already spell
 * it, so on a flow screen it names the wrong system. The word is `lane`.
 * `frontend/DESIGN.md` holds the glossary; this is the sweep that keeps a
 * screen honest to it. Sibling of the `daemon` guard below, and enforced the
 * same way: over rendered text, not over source — which is what leaves
 * `MetaBadge :variant` and the rest of the identifiers alone.
 */
const GIT_WORDS =
  /\b(branch|branches|branching|fork|forks|forked|forking|checkout|checked out|check out|commit|merge|clone|rebase|cherry-pick|worktree|trunk|unsynced|variant|variants)\b/i

const IGNORED_WARNINGS = [
  /Vue Flow parent container needs a width and a height/,
  // jsdom cannot compute SVG layout; vue-flow warns about unmeasurable handles.
  /\[Vue Flow\]/,
]

const unexpected = (spy: { mock: { calls: unknown[][] } }): string[] =>
  spy.mock.calls
    .map((call) => call.map(String).join(' '))
    .filter((message) => !IGNORED_WARNINGS.some((pattern) => pattern.test(message)))

const Empty = defineComponent({ template: '<div />' })

beforeEach(() => {
  document.body.innerHTML = ''
})

afterEach(() => {
  window.localStorage.clear()
  window.sessionStorage.clear()
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
})

function testRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: Empty },
      { path: '/flow', component: Empty },
      { path: '/flow/design/:section?', component: Empty },
      { path: '/flow/:flowId', component: Empty },
      { path: '/flow/:flowId/notebook', component: Empty },
      { path: '/flow/:flowId/compare', component: Empty },
      { path: '/:pathMatch(.*)*', component: Empty },
    ],
  })
}

async function mountClean(component: unknown, path?: string): Promise<string> {
  const router = testRouter()
  if (path) {
    await router.push(path)
    await router.isReady()
  }
  const errors = vi.spyOn(console, 'error').mockImplementation(() => {})
  const warnings = vi.spyOn(console, 'warn').mockImplementation(() => {})

  const wrapper = mount(component as never, {
    global: { plugins: [router, ToastService] },
  })
  await nextTick()
  await nextTick()

  const html = wrapper.html()
  expect(html.length).toBeGreaterThan(0)
  expect(unexpected(errors)).toEqual([])
  expect(unexpected(warnings)).toEqual([])

  const text = wrapper.text()
  wrapper.unmount()
  errors.mockRestore()
  warnings.mockRestore()
  return text
}

const sections = [
  ['foundations', FoundationsSection],
  ['renderers', RenderersSection],
  ['cell-card', CellCardSection],
  ['run-controls', RunControlsSection],
  ['errors', ErrorsSection],
  ['left-panel', LeftPanelSection],
  ['branch-graph', BranchGraphSection],
  ['session', SessionSection],
  ['compare', CompareSection],
  ['pages', PagesSection],
] as const

describe('design system gallery', () => {
  for (const [name, component] of sections) {
    it(`section ${name} mounts without errors and leaks no internals`, async () => {
      const text = await mountClean(component)
      // §10's error-vocabulary rule: no uid, content hash, or memo key on screen.
      expect(text).not.toMatch(/\buid\b/i)
      expect(text).not.toMatch(/memo key/i)
      expect(text).not.toMatch(/\b[0-9a-f]{16,}\b/i)
      // The user runs `lumlflow ui` and stops it with Ctrl+C; what serves it is
      // never a thing they are asked to learn the name of.
      expect(text).not.toMatch(/daemon/i)
      expect(text).not.toMatch(GIT_WORDS)
    })
  }

  /**
   * The gallery is design documentation, and its rationale has a reader — but
   * one paragraph between every specimen and the next reads as chrome. It stays
   * written, one deliberate click away.
   */
  it('holds a specimen’s rationale behind its note toggle until it is asked for', async () => {
    const caption = 'Stale always names its cause in words.'
    const wrapper = mount(GallerySpecimen, {
      props: { title: 'Status vocabulary', caption },
      slots: { default: '<p>specimen</p>' },
    })

    const note = wrapper.get('button')
    expect(note.attributes('aria-expanded')).toBe('false')
    // The button names what it would explain, so it is not a bare glyph to a
    // reader who cannot see it.
    expect(note.attributes('aria-label')).toContain('Status vocabulary')
    const body = wrapper.get(`#${note.attributes('aria-controls')}`)
    expect(body.attributes('style')).toContain('display: none')

    await note.trigger('click')

    expect(note.attributes('aria-expanded')).toBe('true')
    expect(body.attributes('style') ?? '').not.toContain('display: none')
    expect(body.text()).toBe(caption)
    wrapper.unmount()
  })

  it('draws no toggle on a specimen that has nothing to explain', () => {
    const wrapper = mount(GallerySpecimen, {
      props: { title: 'Kind iconography' },
      slots: { default: '<p>specimen</p>' },
    })

    expect(wrapper.find('button').exists()).toBe(false)
    expect(wrapper.text()).toBe('Kind iconographyspecimen')
    wrapper.unmount()
  })

  it('gallery shell mounts and lists every registered section', async () => {
    const text = await mountClean(DesignSystemPage, '/flow/design/foundations')
    for (const [, label] of [
      ['foundations', 'Foundations'],
      ['renderers', 'Renderers'],
      ['cell-card', 'Cell card'],
      ['pages', 'Pages'],
    ]) {
      expect(text).toContain(label)
    }
  })
})

describe('workbench pages', () => {
  it('ignores the retired fixture query keys and opens the live workbench', async () => {
    const daemon = fakeDaemon({ 'flow.open': () => flowStatus() })
    vi.stubGlobal('fetch', daemon.transport)
    vi.stubGlobal('WebSocket', class extends FakeSocket {})
    window.localStorage.setItem(TOKEN_STORAGE_KEY, 'the-token')

    const router = testRouter()
    await router.push(`/flow/${FLOW}?state=running&source=fixture`)
    await router.isReady()
    const wrapper = mount(WorkbenchPage, {
      global: {
        plugins: [router, ToastService],
        stubs: { LiveWorkbench: { template: '<p>live workbench</p>' } },
      },
    })
    await settle()

    expect(wrapper.text()).toContain('live workbench')
    expect(wrapper.text()).not.toContain('this tab is not connected')
    expect(daemon.calls).toContainEqual({ method: 'flow.open', params: { flow: FLOW } })
    wrapper.unmount()
  })

  /**
   * A tab opened without `?token=` has asked nobody anything. Folding it into
   * the not-running state names a failure that has not happened, and sends the
   * reader to restart a server that is already up.
   */
  it('gives a tab with no token its own surface, claiming nothing about the server', async () => {
    for (const [component, path] of [
      [WorkbenchPage, `/flow/${FLOW}?state=running`],
      [ComparePage, `/flow/${FLOW}/compare?source=fixture`],
    ] as const) {
      const text = await mountClean(component, path)
      expect(text).toContain('this tab is not connected')
      expect(text).not.toContain('lumlflow is not running')
      // And never another flow's cells standing in under this one's name.
      expect(text).not.toContain('train_model')
    }
  })

  /**
   * A restarted `lumlflow ui` mints another key, and every call the tab makes
   * with the old one is refused. That is the same nothing as never having had
   * a key — one surface for both, and the dead key dropped so a reload does not
   * present it again.
   */
  it('gives a key the server refuses the same surface, and drops it', async () => {
    vi.stubGlobal('fetch', async () => ({
      ok: false,
      status: 401,
      json: async () => ({
        error: {
          message: "this workspace's key is required — open the address `lumlflow ui` prints",
        },
      }),
    }))

    for (const [component, path] of [
      [WorkbenchPage, `/flow/${FLOW}`],
      [ComparePage, `/flow/${FLOW}/compare`],
    ] as const) {
      window.localStorage.setItem(TOKEN_STORAGE_KEY, 'a-previous-run')
      const router = testRouter()
      await router.push(path)
      await router.isReady()

      const wrapper = mount(component as never, { global: { plugins: [router, ToastService] } })
      await settle()

      expect(wrapper.text()).toContain('this tab is not connected')
      // The refusal's own sentence stays off the page: the notice is the one
      // place the reader is sent from.
      expect(wrapper.text()).not.toContain('key is required')
      expect(window.localStorage.getItem(TOKEN_STORAGE_KEY)).toBeNull()
      wrapper.unmount()
    }

    vi.unstubAllGlobals()
  })
})

/**
 * The shell ships as the product: no draft label and no development surface
 * in a released nav.
 */
describe('the flow shell', () => {
  async function shell(path: string) {
    const router = testRouter()
    await router.push(path)
    await router.isReady()
    const wrapper = mount(FlowShell, { global: { plugins: [router] } })
    await nextTick()
    return wrapper
  }

  it('carries no draft label', async () => {
    const wrapper = await shell('/flow')
    expect(wrapper.text()).not.toMatch(/draft/i)
    wrapper.unmount()
  })

  it('offers a flow’s views only while a flow is open, and only that flow’s', async () => {
    const closed = await shell('/flow')
    expect(closed.text()).not.toContain('Workbench')
    expect(closed.text()).not.toContain('Compare')
    closed.unmount()

    const open = await shell('/flow/other.flow/compare')
    // Real links, so a view of a flow can be opened in a new tab or pasted.
    const links = open.findAll('[role="tab"]').map((tab) => [tab.text(), tab.attributes('href')])
    expect(links).toContainEqual(['Workbench', '/flow/other.flow'])
    expect(links).toContainEqual(['Compare', '/flow/other.flow/compare'])
    // Never the fixture document the draft's tabs stood on.
    expect(open.html()).not.toContain(FLOW)
    open.unmount()
  })

  /**
   * One strip per screen: on the workbench the tabs ride in `WorkbenchTopBar`,
   * which already names the open flow, so the shell draws no second bar there.
   */
  it('draws no strip of its own where the workbench bar carries one', async () => {
    const wrapper = await shell('/flow/other.flow')
    expect(wrapper.findAll('[role="tab"]')).toHaveLength(0)
    wrapper.unmount()
  })

  it('keeps the gallery out of a released nav', async () => {
    vi.stubEnv('DEV', false)
    const wrapper = await shell('/flow/other.flow/compare')

    expect(wrapper.text()).not.toContain('Design system')
    expect(wrapper.text()).not.toMatch(/railroad/i)
    // The flow's own views are unaffected — only the development tabs go.
    expect(wrapper.text()).toContain('Workbench')

    wrapper.unmount()
  })

  it('does not register the design or railroad routes in production', async () => {
    vi.stubEnv('DEV', false)
    vi.resetModules()

    const { default: router } = await import('@/router')

    expect(router.hasRoute('flow-design')).toBe(false)
    expect(router.hasRoute('flow-railroad')).toBe(false)
    expect(router.resolve('/flow/design').name).toBe('flow-work')
    expect(router.resolve('/flow/railroad').name).toBe('flow-work')
  })

  it('offers the gallery while developing', async () => {
    const wrapper = await shell('/flow')
    expect(wrapper.text()).toContain('Design system')
    expect(wrapper.text()).not.toMatch(/railroad/i)
    wrapper.unmount()
  })

  /** Workspace is `MainHeader`'s, and a fact belongs to one place on a screen. */
  it('leaves the workspace switch to the header above it', async () => {
    const wrapper = await shell('/flow/other.flow/compare')
    expect(wrapper.findAll('[role="tab"]').map((tab) => tab.text())).not.toContain('Workspace')
    wrapper.unmount()
  })
})

/**
 * Everything folded away is reachable without a mouse. A disclosure a keyboard
 * cannot open is content that is gone, not content that is one click away.
 */
describe('every disclosure answers the keyboard', () => {
  function panel() {
    return mount(LeftPanel, {
      props: {
        branches,
        cells: cellsByBranch['main'],
        viewedBranch: 'main',
        session,
        env,
        settings,
        journal,
      },
      global: { plugins: [ToastService] },
    })
  }

  it('opens a left-panel section from its header with Enter', async () => {
    const wrapper = panel()
    const header = wrapper
      .findAll('[data-pc-name="accordionheader"]')
      .find((node) => node.text().startsWith('packages'))!

    // A real button: focusable in source order, and Enter/Space are its own.
    expect(header.element.tagName).toBe('BUTTON')
    expect(header.attributes('aria-expanded')).toBe('false')
    expect(header.attributes('aria-controls')).toBeTruthy()

    await header.trigger('keydown', { code: 'Enter' })
    await nextTick()
    expect(header.attributes('aria-expanded')).toBe('true')
    wrapper.unmount()
  })

  it('names the card overflow as the menu it opens', async () => {
    const wrapper = mount(CellOpRow, {
      props: { cell: trainModel, density: 'canvas' },
      global: { plugins: [ToastService] },
    })
    const more = wrapper.findAll('button').find((node) => node.attributes('aria-label') === 'more')!

    expect(more.attributes('aria-haspopup')).toBe('menu')
    await more.trigger('click')
    await nextTick()
    // PrimeVue's Menu owns the roving focus; what this asserts is that the
    // items are real menu items rather than divs with click handlers.
    expect(document.body.querySelectorAll('[role="menuitem"]').length).toBeGreaterThan(0)
    wrapper.unmount()
  })
})

describe('the Agents panel', () => {
  function panelButton(wrapper: ReturnType<typeof mount>, label: string) {
    const found = wrapper.findAll('button').find((candidate) => candidate.text() === label)
    expect(found, `no button labelled "${label}"`).toBeTruthy()
    return found!
  }

  function overlayButton(label: string): HTMLButtonElement {
    const found = [...document.body.querySelectorAll<HTMLButtonElement>('button')].find(
      (candidate) => candidate.textContent?.trim() === label,
    )
    expect(found, `no overlay button labelled "${label}"`).toBeTruthy()
    return found!
  }

  it('selects harnesses, names the config in consent, and waits for approval', async () => {
    const wrapper = mount(AgentsPanel, { props: { harnesses: [CLAUDE_HARNESS] } })

    expect(wrapper.text()).toContain('Claude Code')
    expect(wrapper.text()).toContain('not set up')
    expect(wrapper.text()).toContain('lumlflow guide')

    await wrapper.get('input[type="checkbox"]').setValue(true)
    await panelButton(wrapper, 'Set up').trigger('click')
    await nextTick()

    expect(document.body.textContent).toContain('/home/dana/.claude.json')
    overlayButton('Not now').click()
    await nextTick()
    expect(wrapper.emitted('setup')).toBeUndefined()

    await panelButton(wrapper, 'Set up').trigger('click')
    await nextTick()
    overlayButton('Allow and set up').click()
    await nextTick()

    expect(wrapper.emitted('setup')).toEqual([[['claude-code'], true]])
    wrapper.unmount()
  })

  it('offers state-specific actions and manual repair details', async () => {
    const wrapper = mount(AgentsPanel, {
      props: {
        harnesses: [
          agentHarness({
            id: 'cursor',
            display_name: 'Cursor',
            state: 'out of date',
            action: 'update',
            consent_required: false,
            consent_prompt: null,
            error: 'the config does not parse',
          }),
          agentHarness({
            id: 'jetbrains-ai',
            display_name: 'JetBrains AI',
            can_setup: false,
            action: null,
            config_path: 'Settings > Tools > AI Assistant > MCP',
            shell: false,
            shell_hint: null,
          }),
          agentHarness({
            state: 'set up',
            action: null,
            consent_required: false,
            consent_prompt: null,
          }),
        ],
      },
    })

    expect(wrapper.findAll('input[type="checkbox"]')).toHaveLength(0)
    expect(wrapper.text()).toContain('the config does not parse')
    expect(wrapper.text()).toContain('Settings > Tools > AI Assistant > MCP')
    expect(wrapper.text()).toContain('mcpServers')
    expect(
      wrapper.findAll('button').filter((candidate) => candidate.text() === 'Set up'),
    ).toHaveLength(0)

    await panelButton(wrapper, 'Update').trigger('click')
    await panelButton(wrapper, 'Remove').trigger('click')

    expect(wrapper.emitted('update')).toEqual([['cursor']])
    expect(wrapper.emitted('remove')).toEqual([['claude-code']])
    wrapper.unmount()
  })
})

describe('the card overflow is a menu, not a list of sentences', () => {
  function openMenu(cell = trainModel) {
    const wrapper = mount(CellOpRow, {
      props: { cell, density: 'canvas' as const },
      global: { plugins: [ToastService] },
    })
    const more = wrapper.findAll('button').find((node) => node.attributes('aria-label') === 'more')!
    return { wrapper, more }
  }

  function labels(): string[] {
    return [...document.body.querySelectorAll('[role="menuitem"]')].map((node) =>
      (node.textContent ?? '').trim(),
    )
  }

  it('groups navigate, edit, data and destroy, and stays inside eight items', async () => {
    const { wrapper, more } = openMenu()
    await more.trigger('click')
    await nextTick()

    const items = labels()
    // Eight is the ceiling: past it a menu is a page nobody reads.
    expect(items.length).toBeLessThanOrEqual(8)
    expect(items.slice(0, 2)).toEqual(['expand', 'rename'])
    expect(items).not.toContain('promote to LUML')
    // Destructive last, alone behind its own rule, and coloured as what it is.
    expect(items.at(-1)).toBe('delete from this lane…')
    const destroy = document.body.querySelector('[role="menuitem"]:last-of-type')
    expect(destroy?.className).toContain('flow-menu-danger')
    // Separators, so the groups are visible rather than merely intended.
    expect(document.body.querySelectorAll('[role="separator"]').length).toBe(3)
    wrapper.unmount()
  })

  it('carries a glyph on every item, from the app’s own set', async () => {
    const { wrapper, more } = openMenu()
    await more.trigger('click')
    await nextTick()

    for (const item of document.body.querySelectorAll('[role="menuitem"]')) {
      expect(item.querySelector('svg'), `no glyph on "${item.textContent?.trim()}"`).toBeTruthy()
    }
    wrapper.unmount()
  })

  it('offers a note cell only what a note cell can do', async () => {
    const { wrapper, more } = openMenu(noteCell)
    await more.trigger('click')
    await nextTick()

    const items = labels()
    expect(items).not.toContain('add cell downstream')
    expect(items).not.toContain('promote to LUML')
    expect(items.some((label) => label.startsWith('eager'))).toBe(false)
    wrapper.unmount()
  })
})

describe('a name that is owed is not a warning', () => {
  it('renders the placeholder as the rename gesture, with no banner over the card', async () => {
    const wrapper = mount(CellCard, {
      props: { cell: placeholderCell, density: 'canvas' as const },
      global: { plugins: [ToastService] },
    })

    // No warn field: the state every cell is created in is not a defect.
    expect(wrapper.find('[data-pc-name="message"]').exists()).toBe(false)
    const name = wrapper
      .findAll('button')
      .find((node) => node.attributes('aria-label')?.startsWith('name this cell'))
    expect(name, 'the placeholder name is not a rename affordance').toBeTruthy()
    expect(name?.text()).toContain(placeholderCell.slug)

    await name?.trigger('click')
    expect(wrapper.emitted('rename')).toHaveLength(1)
    wrapper.unmount()
  })

  it('still raises a declaration nobody can act on', () => {
    const wrapper = mount(CellCard, {
      props: { cell: flaggedCell, density: 'canvas' as const },
      global: { plugins: [ToastService] },
    })

    expect(wrapper.find('[data-pc-name="message"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('unknown reference')
    wrapper.unmount()
  })
})

describe('a cell reactivity left alone says so on the card', () => {
  /**
   * The whole point of the field. Without it, a stale cell the threshold
   * declined and a stale cell the runtime forgot about are the same card, and
   * "auto" reads as a setting that does nothing.
   */
  const declined = (autoDeclined: FlowCell['autoDeclined']): FlowCell => ({
    ...trainModel,
    status: 'stale',
    autoDeclined,
  })

  it('names the cost it declined on, and the gesture that resolves it', () => {
    const wrapper = mount(CellCard, {
      props: {
        cell: declined({ reason: 'too-expensive', estimateSeconds: 615, untimed: [] }),
        density: 'canvas' as const,
      },
      global: { plugins: [testRouter(), ToastService] },
    })

    expect(wrapper.text()).toContain('too expensive to refresh on its own')
    expect(wrapper.text()).toContain('run it when you want it')
    wrapper.unmount()
  })

  it('says a cost it has never measured is not a cost it can call cheap', () => {
    const wrapper = mount(CellCard, {
      props: {
        cell: declined({ reason: 'never-timed', estimateSeconds: 0, untimed: ['train_model'] }),
        density: 'canvas' as const,
      },
      global: { plugins: [testRouter(), ToastService] },
    })

    expect(wrapper.text()).toContain('never run here, so its cost is unknown')
    wrapper.unmount()
  })

  it('gives an unmaterialized cell the first-run wording', () => {
    const wrapper = mount(CellCard, {
      props: {
        cell: {
          ...declined({ reason: 'never-timed', estimateSeconds: 0, untimed: ['train_model'] }),
          status: 'unmaterialized',
        },
        density: 'canvas' as const,
      },
      global: { plugins: [testRouter(), ToastService] },
    })

    expect(wrapper.text()).toContain('never run yet — run it once to enable auto-refresh')
    expect(wrapper.text()).not.toContain('cost is unknown')
    wrapper.unmount()
  })

  it('names the failed parent and the edit that unblocks it', () => {
    const detail = 'blocked by failed parent `features`. edit `features` to unblock auto-refresh.'
    const wrapper = mount(CellCard, {
      props: {
        cell: declined({
          reason: 'blocked',
          estimateSeconds: 0,
          untimed: [],
          detail,
        }),
        density: 'canvas' as const,
      },
      global: { plugins: [testRouter(), ToastService] },
    })

    expect(wrapper.text()).toContain(detail)
    wrapper.unmount()
  })

  it('shows the active refresh-failure note instead of a cost gate', () => {
    const wrapper = mount(CellCard, {
      props: {
        cell: {
          ...declined({
            reason: 'refresh-failed',
            estimateSeconds: 0,
            untimed: [],
            detail: 'could not refresh: the workspace interpreter cannot start',
          }),
          status: 'unmaterialized',
        },
        density: 'canvas' as const,
      },
      global: { plugins: [testRouter(), ToastService] },
    })

    expect(wrapper.text()).toContain('could not refresh: the workspace interpreter cannot start')
    expect(wrapper.text()).not.toContain('never run yet')
    expect(wrapper.text()).not.toContain('too expensive')
    wrapper.unmount()
  })

  it('shows an unresolvable reference as the gate the daemon named', () => {
    const wrapper = mount(CellCard, {
      props: {
        cell: {
          ...declined({
            reason: 'unresolvable-reference',
            estimateSeconds: 0,
            untimed: [],
            detail: '`report` needs `nowhere.summary`, which nothing on `main` produces',
          }),
          status: 'unmaterialized',
        },
        density: 'canvas' as const,
      },
      global: { plugins: [testRouter(), ToastService] },
    })

    expect(wrapper.text()).toContain('nowhere.summary')
    expect(wrapper.text()).not.toContain('never run yet')
    expect(wrapper.text()).not.toContain('too expensive')
    wrapper.unmount()
  })

  it('names the removed experiment that makes automatic refresh unsafe', () => {
    const wrapper = mount(CellCard, {
      props: {
        cell: declined({
          reason: 'dangling-experiment',
          estimateSeconds: 0,
          untimed: [],
          detail: '`evaluate` must run because its removed experiment `exp-1` is needed.',
        }),
        density: 'canvas' as const,
      },
      global: { plugins: [testRouter(), ToastService] },
    })

    expect(wrapper.text()).toContain('evaluate')
    expect(wrapper.text()).toContain('removed experiment `exp-1`')
    expect(wrapper.text()).not.toContain('too expensive')
    wrapper.unmount()
  })

  it('renders nothing at all when reactivity has no verdict to give', () => {
    const wrapper = mount(CellCard, {
      props: { cell: declined(undefined), density: 'canvas' as const },
      global: { plugins: [testRouter(), ToastService] },
    })

    expect(wrapper.text()).not.toContain('refresh on its own')
    expect(wrapper.text()).not.toContain('cost is unknown')
    wrapper.unmount()
  })
})

describe('params are declared data', () => {
  it('renders every declared param and offers no way to edit one', () => {
    const wrapper = mount(CodeView, { props: { cell: trainModel, density: 'canvas' } })

    for (const [name, value] of Object.entries(trainModel.params)) {
      expect(wrapper.text()).toContain(name)
      expect(wrapper.text()).toContain(String(value))
    }
    // A dormant slot in v1: editing a param is editing the cell, so the grid
    // carries no field and no apply — the source box below is the one door.
    expect(wrapper.findAll('input')).toEqual([])
    expect(wrapper.text().toLowerCase()).not.toContain('apply')
    wrapper.unmount()
  })
})
