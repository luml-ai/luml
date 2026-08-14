import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { defineComponent, nextTick } from 'vue'
import { createMemoryHistory, createRouter, type Router } from 'vue-router'
import ToastService from 'primevue/toastservice'

import { TOKEN_STORAGE_KEY } from '@/flow/api/token'
import CellCard from '@/flow/workbench/components/card/CellCard.vue'
import CellOpRow from '@/flow/workbench/components/card/CellOpRow.vue'
import CodeView from '@/flow/workbench/components/card/CodeView.vue'
import LeftPanel from '@/flow/workbench/components/panel/LeftPanel.vue'
import PairLink from '@/flow/workbench/components/session/PairLink.vue'
import { CONNECT_PROMPT } from '@/flow/workbench/components/session/connectPrompt'
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
import { settle } from './fakes'

/** The fixture document every workbench route in this suite is addressed by. */
const FLOW = 'churn.flow'

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

/**
 * One exemption, and only one: `.lumlflow/CHECKOUT.md` is a file name a prompt
 * tells an agent to read. File names do not move with the vocabulary — see
 * DESIGN.md, "what a user reads changes; what code calls does not" — so the
 * path is scrubbed before the sentence around it is read.
 */
const spoken = (text: string): string => text.replace(/CHECKOUT\.md/g, 'the sidecar')

/**
 * These mounts hold no token, so the fixture is asked for outright — the same
 * way the gallery links to them. Without it the pages are unconnected tabs.
 */
const AS_FIXTURE = 'source=fixture'

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

/**
 * jsdom ships no clipboard, and what a copy affordance carries is the only
 * string on these surfaces worth asserting: the block is handed a payload and
 * the button must put *that* on the clipboard, whatever the prose around it.
 */
const written: string[] = []

Object.defineProperty(navigator, 'clipboard', {
  configurable: true,
  value: {
    writeText: (text: string) => {
      written.push(text)
      return Promise.resolve()
    },
  },
})

function copied(): string[] {
  return written
}

/** Copy buttons in the teleported overlay, by the label they announce. */
function copyAffordances(): HTMLElement[] {
  return [...document.body.querySelectorAll<HTMLElement>('button[aria-label^="copy the"]')]
}

beforeEach(() => {
  written.length = 0
  document.body.innerHTML = ''
})

function testRouter(): Router {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: Empty },
      { path: '/flow', component: Empty },
      { path: '/flow/design/:section?', component: Empty },
      { path: '/flow/railroad', component: Empty },
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
      expect(spoken(text)).not.toMatch(GIT_WORDS)
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
  it('compare page mounts with the sweep fixture', async () => {
    const text = await mountClean(ComparePage, `/flow/${FLOW}/compare?${AS_FIXTURE}`)
    expect(text).toContain('exp/lr-1e3')
    expect(text).toContain('train_model')
  })

  const states = [
    'running',
    'idle',
    'unpaired',
    'empty',
    'kernel-not-started',
    'not-running',
    'locked',
  ]
  for (const state of states) {
    it(`workbench mounts in state=${state}`, async () => {
      const text = await mountClean(WorkbenchPage, `/flow/${FLOW}?state=${state}`)
      expect(text).not.toMatch(/daemon/i)
      expect(spoken(text)).not.toMatch(GIT_WORDS)
    })
  }

  /**
   * The same sweep over the surfaces the state loop does not reach: the second
   * view of the workbench, the comparison, and the shell's own chrome.
   */
  const surfaces = [
    ['canvas', WorkbenchPage, `/flow/${FLOW}?${AS_FIXTURE}`],
    ['notebook', WorkbenchPage, `/flow/${FLOW}/notebook?${AS_FIXTURE}`],
    ['compare', ComparePage, `/flow/${FLOW}/compare?${AS_FIXTURE}`],
  ] as const
  for (const [name, component, path] of surfaces) {
    it(`${name} speaks none of the vocabulary git owns`, async () => {
      const text = await mountClean(component, path)
      expect(spoken(text)).not.toMatch(GIT_WORDS)
      expect(text).not.toMatch(/daemon/i)
    })
  }

  it('workbench mounts the notebook view with an asset selected', async () => {
    const text = await mountClean(
      WorkbenchPage,
      `/flow/${FLOW}/notebook?asset=train_model&${AS_FIXTURE}`,
    )
    expect(text).toContain('train_model')
  })

  /**
   * A tab opened without `?token=` has asked nobody anything. Folding it into
   * the not-running state names a failure that has not happened, and sends the
   * reader to restart a server that is already up.
   */
  it('gives a tab with no token its own surface, claiming nothing about the server', async () => {
    for (const [component, path] of [
      [WorkbenchPage, `/flow/${FLOW}`],
      [ComparePage, `/flow/${FLOW}/compare`],
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
 * The shell ships as the product: no draft label, no tab standing on a fixture
 * document, and no development surface in a released nav.
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

  it('keeps the gallery and the superseded prototype out of a released nav', async () => {
    vi.stubEnv('DEV', false)
    const wrapper = await shell('/flow/other.flow/compare')

    expect(wrapper.text()).not.toContain('Design system')
    expect(wrapper.text()).not.toMatch(/railroad/i)
    // The flow's own views are unaffected — only the development tabs go.
    expect(wrapper.text()).toContain('Workbench')

    wrapper.unmount()
    vi.unstubAllEnvs()
  })

  it('offers both while developing', async () => {
    const wrapper = await shell('/flow')
    expect(wrapper.text()).toContain('Design system')
    expect(wrapper.text()).toContain('Railroad')
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

  it('names the pairing link as the overlay trigger it is', async () => {
    const wrapper = mount(PairLink)
    const trigger = wrapper.find('button')

    expect(trigger.attributes('aria-haspopup')).toBe('dialog')
    expect(trigger.attributes('aria-expanded')).toBe('false')

    await trigger.trigger('click')
    await nextTick()
    // Pairing is one thing handed over, so the popover offers one way to take
    // it — a second command beside it is what this surface used to be.
    expect(copyAffordances()).toHaveLength(1)
    // Opening it is the ask: a live surface fetches the real prompt here.
    expect(wrapper.emitted('open')).toHaveLength(1)
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

/**
 * Pairing hands the agent a prompt it connects back over — nothing here runs
 * the agent, so nothing here is a command. What the popover must get right is
 * that the block the reader copies carries exactly the prompt it was handed.
 */
describe('pairing hands over a prompt, not a command', () => {
  const DAEMON_PROMPT = 'You are paired with the lumlflow flow `churn` in `/tmp/project`.'

  async function openPairing(prompt?: string) {
    const wrapper = mount(PairLink, { props: { prompt } })
    await wrapper.find('button').trigger('click')
    await nextTick()
    return wrapper
  }

  it('carries the prompt the surface was handed into the clipboard', async () => {
    const wrapper = await openPairing(DAEMON_PROMPT)

    await copyAffordances()[0].click()

    expect(copied()).toEqual([DAEMON_PROMPT])
    wrapper.unmount()
  })

  it('falls back to the flow’s own prompt where nothing has answered', async () => {
    // The fixture routes and the gallery mount it with no answer in hand, and a
    // popover that is dead there is the bug §3 records — not an empty state.
    const wrapper = await openPairing()

    await copyAffordances()[0].click()

    expect(copied()).toEqual([CONNECT_PROMPT])
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
    // Frequency order, with the two the footer used to carry at the top.
    expect(items.slice(0, 2)).toEqual(['expand', 'send to agent'])
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
      global: { plugins: [ToastService] },
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
      global: { plugins: [ToastService] },
    })

    expect(wrapper.text()).toContain('never run here, so its cost is unknown')
    wrapper.unmount()
  })

  it('renders nothing at all when reactivity has no verdict to give', () => {
    const wrapper = mount(CellCard, {
      props: { cell: declined(undefined), density: 'canvas' as const },
      global: { plugins: [ToastService] },
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
