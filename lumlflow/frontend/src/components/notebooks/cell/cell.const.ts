import type { CellStaleState } from '@/api/slices/workspace/workspace.interface'
import type { LucideIcon } from 'lucide-vue-next'
import type { MenuPassThroughOptions, TabListPassThroughOptions } from 'primevue'
import {
  AlertTriangle,
  ChartBar,
  ChartSpline,
  CheckCircle2,
  CircleDashed,
  CircuitBoard,
  ClipboardCheck,
  FlaskConical,
  RefreshCw,
  Save,
  StickyNote,
  Table2,
} from 'lucide-vue-next'
import { NAME_REQUIRED_MESSAGE } from '@/constants/forms'

export const CELL_STATE_LABELS: Record<CellStaleState, string> = {
  synced: 'Up to date',
  unsynced: 'Out of date',
  unmaterialized: 'Not materialized',
  failed: 'Failed',
}

export const CELL_STATE_ICONS: Record<CellStaleState, LucideIcon> = {
  synced: CheckCircle2,
  unsynced: RefreshCw,
  unmaterialized: CircleDashed,
  failed: AlertTriangle,
}

export const CELL_NAME_PATTERN = /^[a-z][a-z0-9_]*$/

const PYTHON_KEYWORDS = new Set([
  'and',
  'as',
  'assert',
  'async',
  'await',
  'break',
  'class',
  'continue',
  'def',
  'del',
  'elif',
  'else',
  'except',
  'finally',
  'for',
  'from',
  'global',
  'if',
  'import',
  'in',
  'is',
  'lambda',
  'nonlocal',
  'not',
  'or',
  'pass',
  'raise',
  'return',
  'try',
  'while',
  'with',
  'yield',
])

export const CELL_NAME_HINT =
  'Lowercase letters, digits and underscores, starting with a letter. E.g. my_cell_1'

export const CELL_NAME_INVALID_MESSAGE =
  'Use only lowercase letters, digits and underscores, and start with a letter'

export function getCellNameError(
  name: string,
  existingSlugs: string[],
  currentSlug?: string,
): string | null {
  if (!name) return NAME_REQUIRED_MESSAGE
  if (!CELL_NAME_PATTERN.test(name)) return CELL_NAME_INVALID_MESSAGE
  if (PYTHON_KEYWORDS.has(name)) return `"${name}" is a Python keyword`
  const isTaken = existingSlugs.some(
    (slug) => slug !== currentSlug && slug.toLowerCase() === name.toLowerCase(),
  )
  if (isTaken) return `"${name}" already exists`
  return null
}

export function toCellName(slug: string): string {
  const name = slug
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, '_')
    .replace(/^_+|_+$/g, '')
  return /^[a-z]/.test(name) ? name : `cell_${name}`.replace(/_+$/, '')
}

export const CELL_HEADER_MENU_PT: MenuPassThroughOptions = {
  root: {
    style: 'background-color: var(--p-card-background);',
  },
}

export const CELL_TABS_LIST_PT: TabListPassThroughOptions = {
  root: {
    class: 'bg-transparent!',
  },
  tabList: {
    style: 'border-left: none; border-top: none; border-right: none; ',
  },
}

export const CELL_OUTPUT_KIND_ICONS: Record<string, LucideIcon> = {
  plot: ChartSpline,
  frame: Table2,
  dataset: Table2,
  model: CircuitBoard,
  experiment: FlaskConical,
  metric: ChartBar,
  eval: ClipboardCheck,
  checkpoint: Save,
  note: StickyNote,
}

export const DEFAULT_OUTPUT_KIND_ICON: LucideIcon = ChartBar

/**
 * What a card says while a paired agent is inside a daemon call on it. The
 * wire names the method; the card names the gesture. A method not listed
 * reads as "working on", which is true of all of them.
 */
export const AGENT_TOOL_VERBS: Record<string, string> = {
  'cells.edit': 'editing',
  'cells.new': 'adding',
  'cells.show': 'reading',
  'cells.logs': 'reading logs of',
  'cells.reorder': 'moving',
  'cells.delete': 'deleting',
  'cells.eager': 'changing',
  'asset.preview': 'inspecting',
  'asset.page': 'inspecting',
  adopt: 'adopting',
  rename: 'renaming',
  run: 'running',
}

export function agentToolVerb(tool: string): string {
  return AGENT_TOOL_VERBS[tool] ?? 'working on'
}
