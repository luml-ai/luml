import { computed, getCurrentScope, onScopeDispose, ref, shallowRef, watch } from 'vue'
import type { ComputedRef, Ref } from 'vue'

import type {
  AssetView,
  BranchDiff,
  BranchRecord,
  DiffVersionSide,
  StaleState,
} from '@/flow/api/types'
import type {
  CompareBranchColumn,
  CompareTrackerLink,
  CompareView,
  DefinitionDivergence,
  MaterializationRow,
  ShapelessDifference,
} from '../model/types'
import type { ParamValue } from '../model/types'
import { assetKindOf, previewFrom } from './preview'
import type { FlowSessionHandle } from './useFlowSession'

export interface CompareHandle {
  compare: ComputedRef<CompareView>
  assets: ComputedRef<string[]>
  focused: ComputedRef<string | null>
  ready: ComputedRef<boolean>
  loading: Ref<boolean>
  error: Ref<string | null>
  refresh: () => Promise<void>
}

const EMPTY: CompareView = {
  branches: [],
  sharedMetric: '',
  definitionDivergences: [],
  materializationRows: [],
  shapelessDifferences: [],
  warnings: [],
  trackerLinks: [],
}

export function useCompare(
  session: FlowSessionHandle,
  branches: Ref<string[]>,
  asset: Ref<string | null>,
): CompareHandle {
  const diff = shallowRef<BranchDiff | null>(null)
  const records = ref<BranchRecord[]>([])
  const views = shallowRef<Record<string, AssetView | null>>({})
  const shown = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const assets = computed(() => [
    ...(diff.value?.definition ?? []).map((entry) => entry.slug),
    ...(diff.value?.materialization ?? []).map((entry) => entry.slug),
  ])

  const focused = computed<string | null>(() => {
    const wanted = asset.value
    if (wanted && assets.value.includes(wanted)) return wanted
    return assets.value[0] ?? null
  })

  // Bumped whenever what is being compared changes: an answer about the set of
  // branches that was asked about a moment ago would land as this one's.
  let asked = 0

  async function load(): Promise<void> {
    const generation = (asked += 1)
    if (branches.value.length < 2) {
      diff.value = null
      error.value = null
      return
    }
    loading.value = true
    try {
      const flow = session.brief.value?.path
      const [compared, tree] = await Promise.all([
        session.request('diff', { flow, branches: [...branches.value] }),
        session.request('tree', { flow }),
      ])
      if (generation !== asked) return
      diff.value = compared
      records.value = tree.branches
      error.value = null
    } catch (failure) {
      if (generation !== asked) return
      diff.value = null
      error.value = failure instanceof Error ? failure.message : String(failure)
    } finally {
      if (generation === asked) loading.value = false
    }
  }

  let read = 0

  async function loadPreviews(): Promise<void> {
    const generation = (read += 1)
    const target = focused.value
    if (!target) {
      views.value = {}
      shown.value = null
      return
    }
    const flow = session.brief.value?.path
    const answers = await Promise.all(
      branches.value.map(async (branch) => {
        try {
          const view = await session.request('asset.preview', { flow, branch, target })
          return [branch, view] as const
        } catch {
          return [branch, null] as const
        }
      }),
    )
    // Columns of one asset beside a heading naming another is the one way this
    // screen could mislead outright; a superseded read is dropped instead.
    if (generation !== read) return
    views.value = Object.fromEntries(answers)
    shown.value = target
  }

  watch([branches, session.revision], () => void load(), { immediate: true, deep: true })
  watch([focused, diff], () => void loadPreviews(), { immediate: true })

  const compare = computed<CompareView>(() => {
    const compared = diff.value
    if (compared === null) return EMPTY
    const settled = new Map(
      records.value.map((record) => [record.branch, record.last_intent?.settled ?? false]),
    )
    const columns = compared.branches.map((branch) =>
      column(branch, views.value[branch]?.preview ?? null, settled.get(branch) ?? false),
    )
    return {
      branches: columns,
      sharedMetric: sharedMetric(columns),
      definitionDivergences: compared.definition.map(divergence),
      materializationRows: compared.materialization.map(row),
      shapelessDifferences: compared.shapeless.map(shapeless),
      warnings: compared.integrity.map((warning) => ({
        kind: warning.kind,
        message: warning.message,
        affectedBranches: warning.branches,
      })),
      trackerLinks: trackerLinks(compared.branches, views.value),
    }
  })

  const stopState = session.onState((frame) => {
    if (frame.state !== 'experiment_removed') return
    if (frame.lane && !branches.value.includes(frame.lane)) return
    void loadPreviews()
  })
  if (getCurrentScope()) onScopeDispose(stopState)

  return {
    compare,
    assets,
    focused,
    ready: computed(() => focused.value !== null && shown.value === focused.value),
    loading,
    error,
    refresh: load,
  }
}

const SECTION = /^\*\*(.+)\*\*$/

function column(
  branch: string,
  stored: AssetView['preview'],
  settled: boolean,
): CompareBranchColumn {
  const preview = previewFrom(stored)
  if (preview.type === 'experiment') {
    const recorded = [preview.mainMetric, ...preview.metrics].filter(
      (metric): metric is NonNullable<typeof metric> => metric !== undefined,
    )
    const scores = Object.fromEntries(
      recorded.flatMap((metric) =>
        typeof metric.value === 'number' ? [[metric.name, metric.value]] : [],
      ),
    )
    return {
      branch,
      headlineMetric:
        recorded.length === 1 && typeof recorded[0].value === 'number'
          ? { name: recorded[0].name, value: recorded[0].value }
          : undefined,
      scores,
      curve: preview.curves.find((curve) => curve.points.length),
      settled,
      heldKind: 'experiment',
    }
  }
  const sections = new Map<string, Record<string, number>>()
  let section = ''
  let curve: CompareBranchColumn['curve']
  if (preview.type === 'blocks') {
    for (const block of preview.blocks) {
      if (block.block === 'markdown') {
        section = SECTION.exec(block.text.trim())?.[1] ?? section
      } else if (block.block === 'kv') {
        const held = sections.get(section) ?? {}
        for (const [name, value] of Object.entries(block.entries)) {
          if (typeof value === 'number') held[name] = value
        }
        sections.set(section, held)
      } else if (block.block === 'series' && curve === undefined && block.points.length) {
        curve = { name: block.name, points: block.points }
      }
    }
  }
  const labelled = [...sections.keys()].some((name) => name !== '')
  const scores: Record<string, number> = labelled
    ? (sections.get('metrics') ?? {})
    : Object.assign({}, ...sections.values())
  const names = Object.keys(scores)
  return {
    branch,
    headlineMetric: names.length === 1 ? { name: names[0], value: scores[names[0]] } : undefined,
    scores,
    curve,
    settled,
    heldKind: stored === null ? undefined : assetKindOf(stored.kind),
  }
}

function sharedMetric(columns: CompareBranchColumn[]): string {
  const names = new Set(columns.map((entry) => entry.curve?.name).filter(Boolean))
  return names.size === 1 ? [...names][0]! : ''
}

function divergence(entry: BranchDiff['definition'][number]): DefinitionDivergence {
  const sides = new Map<number, DiffVersionSide[]>()
  for (const side of entry.versions) {
    sides.set(side.step, [...(sides.get(side.step) ?? []), side])
  }
  return {
    slug: entry.slug,
    sides: [...sides.entries()]
      .sort(([left], [right]) => left - right)
      .map(([step, grouped]) => ({
        branches: grouped.map((side) => side.branch),
        params: params(grouped[0].params),
        version: `step ${step}`,
      })),
  }
}

function row(entry: BranchDiff['materialization'][number]): MaterializationRow {
  return {
    slug: entry.slug,
    kind: 'chip',
    byBranch: Object.fromEntries(
      entry.results.map((side) => [
        side.branch,
        { label: STATES[side.state], state: side.state === 'synced' ? 'same' : 'missing' },
      ]),
    ),
  }
}

const STATES: Record<StaleState, string> = {
  synced: 'materialized',
  unsynced: 'stale',
  unmaterialized: 'never run',
  failed: 'failed',
}

function shapeless(entry: BranchDiff['shapeless'][number]): ShapelessDifference {
  const carried = Object.entries(entry.branches).filter(([, name]) => name !== null)
  const named = new Set(carried.map(([, name]) => name))
  const missing = Object.entries(entry.branches)
    .filter(([, name]) => name === null)
    .map(([branch]) => branch)
  return {
    slug: entry.slug,
    what:
      named.size > 1
        ? `named ${carried.map(([branch, name]) => `\`${name}\` on ${branch}`).join(', ')}`
        : `not on ${missing.join(', ')}`,
    branches: carried.map(([branch]) => branch),
  }
}

function trackerLinks(
  branches: string[],
  views: Record<string, AssetView | null>,
): CompareTrackerLink[] {
  return branches.flatMap((branch) => {
    const view = views[branch]
    if (!view?.tracker) return []
    return [
      {
        branch,
        slug: view.slug,
        output: view.output,
        tracker: view.tracker,
      },
    ]
  })
}

function params(declared: Record<string, unknown>): Record<string, ParamValue> {
  return Object.fromEntries(
    Object.entries(declared).map(([name, value]) => [
      name,
      typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean'
        ? value
        : value === null || value === undefined
          ? null
          : JSON.stringify(value),
    ]),
  )
}
