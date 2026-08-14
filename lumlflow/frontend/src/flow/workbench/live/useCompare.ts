/**
 * 2–5 branches side by side, out of the daemon's own comparison.
 *
 * Every verdict here arrives computed. **Which** divergence an asset shows —
 * someone edited the cell, or the same code was fed something different — is
 * the daemon's call, and so is whether the comparison is comparable at all:
 * pin-at-fork is what keeps a sweep honest, and where it stopped holding the
 * runtime says so rather than leaving a reader to notice. Nothing below
 * re-derives either.
 *
 * What this file *does* add is the reading: the columns are one focused asset
 * across the branches, so the numbers under a comparison are the numbers of one
 * cell rather than a heap of every metric in the flow. The focus is a selection
 * like any other — the URL's asset when the compared branches carry it, else
 * the first thing the daemon reported as diverging.
 *
 * One thing it refuses to do is name a winner. No output records whether its
 * metric reads up or down, so a column marked "best" would be a claim nobody
 * measured; the reader picks the winner and the adopt bar carries it out.
 */

import { computed, ref, shallowRef, watch } from 'vue'
import type { ComputedRef, Ref } from 'vue'

import type {
  BranchDiff,
  BranchRecord,
  DiffSide,
  DiffVersionSide,
  MaterializedOutput,
  StaleState,
  StoredPreview,
} from '@/flow/api/types'
import type {
  CompareArtifactLink,
  CompareBranchColumn,
  CompareView,
  DefinitionDivergence,
  MaterializationRow,
  ShapelessDifference,
} from '../model/types'
import type { ParamValue } from '../model/types'
import { assetKindOf, previewFrom } from './preview'
import type { FlowSessionHandle } from './useFlowSession'

export interface CompareHandle {
  /** The comparison as the compare cluster consumes it. */
  compare: ComputedRef<CompareView>
  /** Assets the comparison can lead with, in the order the daemon reported. */
  assets: ComputedRef<string[]>
  /** The asset the columns and the adopt bar are about — the URL's, resolved. */
  focused: ComputedRef<string | null>
  /** The columns describe the focused asset — before this they describe nothing. */
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
  artifacts: [],
}

/** What leaves the flow, and therefore what a tracker screen could hold. */
const NATIVE = new Set(['experiment', 'model', 'dataset'])

export function useCompare(
  session: FlowSessionHandle,
  branches: Ref<string[]>,
  asset: Ref<string | null>,
): CompareHandle {
  const diff = shallowRef<BranchDiff | null>(null)
  const records = ref<BranchRecord[]>([])
  const previews = shallowRef<Record<string, StoredPreview | null>>({})
  /** Which asset the previews in hand are of — none, until a read lands. */
  const shown = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const assets = computed(() => [
    ...(diff.value?.definition ?? []).map((entry) => entry.slug),
    ...(diff.value?.materialization ?? []).map((entry) => entry.slug),
  ])

  /**
   * The URL's asset when the comparison has something to say about it, else the
   * daemon's first divergence: an asset that diverges nowhere would lead with
   * four identical columns. The focus lives in the URL and nowhere else, so the
   * link is the comparison and the daemon hears about it through `set_focus`.
   */
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
      const flow = session.brief.value?.flow
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

  /**
   * The focused asset's stored preview on each branch — the kernel-free tier,
   * so laying four branches side by side starts no process. A branch that has
   * never run it answers with nothing, which is what the column then says.
   */
  async function loadPreviews(): Promise<void> {
    const generation = (read += 1)
    const target = focused.value
    if (!target) {
      previews.value = {}
      shown.value = null
      return
    }
    const flow = session.brief.value?.flow
    const answers = await Promise.all(
      branches.value.map(async (branch) => {
        try {
          const view = await session.request('asset.preview', { flow, branch, target })
          return [branch, view.preview] as const
        } catch {
          // A branch that does not carry the cell is not a failed comparison —
          // the shapeless table is where that difference is already reported.
          return [branch, null] as const
        }
      }),
    )
    // Columns of one asset beside a heading naming another is the one way this
    // screen could mislead outright; a superseded read is dropped instead.
    if (generation !== read) return
    previews.value = Object.fromEntries(answers)
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
      column(branch, previews.value[branch] ?? null, settled.get(branch) ?? false),
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
      artifacts: artifacts(compared, focused.value),
    }
  })

  return {
    compare,
    assets,
    focused,
    // A column reading "nothing materialized here" because its preview is still
    // on its way is a wrong answer, not a slow one.
    ready: computed(() => focused.value !== null && shown.value === focused.value),
    loading,
    error,
    refresh: load,
  }
}

// --- the columns ------------------------------------------------------------

/** A preview section header, as the kernel writes one above its entries. */
const SECTION = /^\*\*(.+)\*\*$/

/**
 * One branch's reading of the focused asset: the numbers its stored preview
 * holds, and the curve if it kept one.
 *
 * An experiment carries its params and its metrics as two labelled sections,
 * and only one of them is a result — a comparison listing `lr` beside `auc`
 * under "final results" would be reading a setting as an outcome. Where the
 * payload labels a `metrics` section, that is the one taken; a payload with no
 * sections at all — a plain metric dict — is all numbers and all results.
 *
 * The headline is a headline only when the output has exactly one number to
 * lead with. Picking one out of six would be ranking them, and no output
 * records which of its numbers leads or which way it reads.
 *
 * Most kinds record no numbers at all — a frame previews as its head rows, a
 * plot as an image — so having none is the ordinary case and not the same fact
 * as having nothing. The kind is carried for exactly that distinction.
 */
function column(
  branch: string,
  stored: StoredPreview | null,
  settled: boolean,
): CompareBranchColumn {
  const preview = previewFrom(stored)
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
  // A payload with no headers at all — a plain metric dict — is all numbers and
  // all results. One that labels its sections holds its results in exactly one
  // of them, and a run that recorded params and never got to its metrics has no
  // results at all: reading its `lr` as one would report a setting somebody
  // chose as a number somebody measured.
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

/** The name the overlaid curves share, when every drawn one carries the same. */
function sharedMetric(columns: CompareBranchColumn[]): string {
  const names = new Set(columns.map((entry) => entry.curve?.name).filter(Boolean))
  return names.size === 1 ? [...names][0]! : ''
}

// --- the two divergence kinds -----------------------------------------------

/**
 * One side per distinct version, not per branch: two branches holding the same
 * version are one side of the fork, and drawing them apart would read as an
 * edit neither of them made. Versions are told apart by the step they were
 * accepted at — the number the timeline and a rewind already address them by.
 */
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

/**
 * One row per asset, whatever it produced: everything below an edit differs by
 * inputs alone, and a row per output would fan the same fact across a sweep.
 * The chip says what the branch holds — better and worse are not on offer,
 * because no output records which way its numbers read.
 */
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

/** A cell one branch does not carry, or one whose name moved. */
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

// --- what left the flow -----------------------------------------------------

/**
 * The focused asset's outputs that leave the flow, and where each branch's
 * stands. There is no artifact screen to open from here, so the row says what
 * it is and the chips say whether the upload landed — a link that went nowhere
 * would be worse than the sentence.
 */
function artifacts(compared: BranchDiff, slug: string | null): CompareArtifactLink[] {
  if (slug === null) return []
  const sides: DiffSide[] =
    compared.definition.find((entry) => entry.slug === slug)?.versions ??
    compared.materialization.find((entry) => entry.slug === slug)?.results ??
    []
  const kinds = new Map<string, string>()
  for (const side of sides) {
    for (const output of side.outputs) {
      if (NATIVE.has(output.declared)) kinds.set(output.name, output.declared)
    }
  }
  return [...kinds].map(([output, kind]) => ({
    slug,
    output,
    kind: kind as CompareArtifactLink['kind'],
    // What it is, in the four-word vocabulary the cell declared it under.
    label: `${output} · ${kind}`,
    href: '',
    byBranch: Object.fromEntries(
      sides.map((side) => [side.branch, uploadState(side.outputs, output)]),
    ),
  }))
}

function uploadState(outputs: MaterializedOutput[], name: string): string {
  const output = outputs.find((entry) => entry.name === name)
  if (output === undefined) return 'not materialized'
  return output.uploaded ? 'uploaded' : 'not uploaded'
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
