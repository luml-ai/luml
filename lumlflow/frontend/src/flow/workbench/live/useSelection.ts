import { ref, watch } from 'vue'
import type { Ref } from 'vue'
import type { RouteLocationNormalizedLoaded } from 'vue-router'

import { TOKEN_PARAM } from '@/flow/api/token'

export type WorkbenchView = 'canvas' | 'notebook'

export interface SelectionOptions {
  defaultBranch: Ref<string>
}

export interface SelectionHandle {
  view: Ref<WorkbenchView>
  viewedBranch: Ref<string>
  selectedSlug: Ref<string | null>
  compared: Ref<string[]>
  path: () => string
  query: () => string
}

const NOTEBOOK = '/notebook'

export function useSelection(
  route: RouteLocationNormalizedLoaded,
  options: SelectionOptions,
): SelectionHandle {
  const base = route.path.endsWith(NOTEBOOK) ? route.path.slice(0, -NOTEBOOK.length) : route.path
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
