/**
 * What the user is looking at: the viewed branch, the selected asset, and the
 * open comparison, mirrored in the URL.
 *
 * **In the URL** because a link to a cell on a branch is the addressing story
 * the whole product uses: slug and branch name, never a number. Which view is
 * up is the route itself (`/flow/:flowId` and `/flow/:flowId/notebook`), so a
 * link to the notebook opens the notebook. The mirror is
 * `history.replaceState` rather than `router.replace` because the shell keys
 * its `RouterView` on the full path, and a route change would remount the page
 * — refitting the canvas and closing the drawer — on every click.
 */

import { ref, watch } from 'vue'
import type { Ref } from 'vue'
import type { RouteLocationNormalizedLoaded } from 'vue-router'

import { TOKEN_PARAM } from '@/flow/api/token'

export type WorkbenchView = 'canvas' | 'notebook'

export interface SelectionOptions {
  /** Where the URL says nothing — the branch the worktree is bound to. */
  defaultBranch: Ref<string>
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
    // Query keys owned by another surface are not this selection's to remove.
    for (const [name, value] of Object.entries(route.query)) {
      if (OWNED.includes(name) || name === TOKEN_PARAM || typeof value !== 'string') continue
      params.set(name, value)
    }
    return params.toString()
  }

  watch([view, selectedSlug, viewedBranch, compared, options.defaultBranch], () => {
    const search = query()
    if (typeof window !== 'undefined') {
      window.history.replaceState(
        window.history.state,
        '',
        `${path()}${search ? `?${search}` : ''}`,
      )
    }
  })

  return { view, viewedBranch, selectedSlug, compared, path, query }
}

function queryOne(route: RouteLocationNormalizedLoaded, name: string): string | null {
  const value = route.query[name]
  return typeof value === 'string' && value ? value : null
}

function queryList(route: RouteLocationNormalizedLoaded, name: string): string[] {
  const value = queryOne(route, name)
  return value ? value.split(',').filter(Boolean) : []
}
