/**
 * What the user is looking at: the viewed branch, the selected asset, the open
 * comparison — in the URL, and reported to the daemon.
 *
 * **In the URL** because a link to a cell on a branch is the addressing story
 * the whole product uses: slug and branch name, never a number. Which view is
 * up is the route itself (`/flow/:flowId` and `/flow/:flowId/notebook`), so a
 * link to the notebook opens the notebook. The mirror is
 * `history.replaceState` rather than `router.replace` because the shell keys
 * its `RouterView` on the full path, and a route change would remount the page
 * — refitting the canvas and closing the drawer — on every click.
 *
 * **Reported** because `lumlflow context` and the MCP focus resource are what
 * an agent reads to know where its human is, and the daemon has no other way to
 * learn it. It is a report and never a guess: absent one, the brief omits focus
 * rather than pointing an agent at whatever happens to be first. Debounced,
 * because dragging across a canvas is one focus, not forty.
 */

import { getCurrentScope, onScopeDispose, ref, watch } from 'vue'
import type { Ref } from 'vue'
import type { RouteLocationNormalizedLoaded } from 'vue-router'

import type { FlowSessionHandle } from './useFlowSession'

export type WorkbenchView = 'canvas' | 'notebook'

const REPORT_DEBOUNCE_MS = 250

export interface SelectionOptions {
  session: FlowSessionHandle
  /** Where the URL says nothing — the branch the worktree is bound to. */
  defaultBranch: Ref<string>
  /** Off in the gallery and in tests that assert the URL alone. */
  report?: boolean
}

export interface SelectionHandle {
  view: Ref<WorkbenchView>
  viewedBranch: Ref<string>
  selectedSlug: Ref<string | null>
  compared: Ref<string[]>
  /** The path this selection mirrors — the view is a route, not a parameter. */
  path: () => string
  /** The query string this selection mirrors — asserted directly in tests. */
  query: () => string
  reportFocus: () => Promise<void>
}

/** The notebook is a route of its own: `/flow/:flowId/notebook`. */
const NOTEBOOK = '/notebook'

export function useSelection(
  route: RouteLocationNormalizedLoaded,
  options: SelectionOptions,
): SelectionHandle {
  const base = route.path.endsWith(NOTEBOOK) ? route.path.slice(0, -NOTEBOOK.length) : route.path
  // The route says which view this is; `?view=` is honoured too, so links
  // written before the notebook had a path of its own still land where they meant.
  const view = ref<WorkbenchView>(
    route.path.endsWith(NOTEBOOK) || queryOne(route, 'view') === 'notebook' ? 'notebook' : 'canvas',
  )
  const selectedSlug = ref<string | null>(queryOne(route, 'asset'))
  const viewedBranch = ref<string>(queryOne(route, 'branch') ?? options.defaultBranch.value)
  const compared = ref<string[]>(queryList(route, 'compare'))

  const OWNED = ['view', 'asset', 'branch', 'compare']

  function path(): string {
    return view.value === 'notebook' ? `${base}${NOTEBOOK}` : base
  }

  function query(): string {
    const params = new URLSearchParams()
    if (selectedSlug.value) params.set('asset', selectedSlug.value)
    if (viewedBranch.value !== options.defaultBranch.value) params.set('branch', viewedBranch.value)
    if (compared.value.length > 0) params.set('compare', compared.value.join(','))
    // Whatever else the URL carried stays: `?state=` is what puts the workbench
    // on fixtures, and dropping it on the first click would swap the data
    // source out from under a gallery link.
    for (const [name, value] of Object.entries(route.query)) {
      if (OWNED.includes(name) || typeof value !== 'string') continue
      params.set(name, value)
    }
    return params.toString()
  }

  async function reportFocus(): Promise<void> {
    if (options.report === false) return
    await options.session
      .request('set_focus', {
        flow: options.session.brief.value?.path,
        branch: viewedBranch.value,
        asset: selectedSlug.value,
        compare: compared.value,
      })
      // A brief that lost its focus line is not worth a surfaced failure: the
      // report is the least of what this session is doing.
      .catch(() => {})
  }

  let pending: ReturnType<typeof setTimeout> | null = null

  watch([view, selectedSlug, viewedBranch, compared], () => {
    const search = query()
    if (typeof window !== 'undefined') {
      window.history.replaceState(
        window.history.state,
        '',
        `${path()}${search ? `?${search}` : ''}`,
      )
    }
    if (pending !== null) clearTimeout(pending)
    pending = setTimeout(() => {
      pending = null
      void reportFocus()
    }, REPORT_DEBOUNCE_MS)
  })

  if (getCurrentScope()) {
    onScopeDispose(() => {
      if (pending !== null) clearTimeout(pending)
    })
  }

  return { view, viewedBranch, selectedSlug, compared, path, query, reportFocus }
}

function queryOne(route: RouteLocationNormalizedLoaded, name: string): string | null {
  const value = route.query[name]
  return typeof value === 'string' && value ? value : null
}

function queryList(route: RouteLocationNormalizedLoaded, name: string): string[] {
  const value = queryOne(route, name)
  return value ? value.split(',').filter(Boolean) : []
}
