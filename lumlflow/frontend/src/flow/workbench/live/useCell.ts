/**
 * One cell's card, assembled from what the daemon recorded about it.
 *
 * The slice already carries every verdict — state, causes, cost, whether the
 * result was reused, whether the env has moved since — so nothing here decides
 * anything a card shows about staleness. What this adds is the rest of the card:
 * the declarations and source behind the `code` tab, a stored preview per output
 * tab, the log artifact of the run this branch observed, and the live console
 * while one is in flight.
 *
 * Everything but the summary is pulled **on demand**. A canvas of twenty cards
 * that fetched four previews, a source and a log apiece on every journal
 * transaction would spend its life refetching; a card fetches the tab it is
 * showing, and re-fetches when the journal moves under it, because a preview
 * from before the last run is a stale picture of a fresh value.
 *
 * The tab the card shows is reported back here rather than guessed at: which
 * payload is worth pulling is exactly the question the tab strip answers.
 */

import { computed, ref, shallowRef, watch } from 'vue'
import type { ComputedRef, Ref } from 'vue'

import type { FlowStream } from '@/flow/api/stream'
import type {
  AssetDownload,
  CellDetail,
  CellSummary,
  MaterializedOutput,
  OutputSpec,
} from '@/flow/api/types'
import type {
  ActorRef,
  AutoDeclinedInfo,
  CellOutput,
  CellStatus,
  DeclaredType,
  FlowCell,
  ParamValue,
  PreviewValue,
  ProvenanceInfo,
  StaleInfo,
  TimingInfo,
  ValuePage,
} from '../model/types'
import { assetKindOf, previewFrom } from './preview'
import type { FlowSessionHandle } from './useFlowSession'
import { useRunLogs } from './useRunLogs'

/** Tab ids the card reports: `out:<name>`, or one of the implicit three. */
export type CellTabId = string

/** Where a pager wants to go, in windows rather than in row numbers. */
export type PageMove = 'first' | 'next' | 'previous'

export interface LiveCellOptions {
  session: FlowSessionHandle
  stream: FlowStream
  branch: Ref<string>
  summary: Ref<CellSummary>
}

export interface LiveCellHandle {
  cell: ComputedRef<FlowCell>
  /**
   * The version an edit of this card would be based on. It is a hash, so it
   * belongs nowhere on screen — it rides with the edit and comes back as the
   * conflict when the head has moved on since.
   */
  base: ComputedRef<string | null>
  /** What the card is showing. Setting it is what pulls the payload behind it. */
  showing: Ref<CellTabId>
  /** The run in flight for this cell, when the session has one. */
  runId: ComputedRef<string | null>
  /** Rows read out of the value itself — the drawer's paging, kernel-served. */
  rows: Ref<ValuePage | null>
  paging: Ref<boolean>
  readPage: (output: string, move: PageMove) => Promise<void>
  /** Pull the run's log artifact even when the reader is not on the logs tab. */
  readLogs: () => void
  download: (output: string) => Promise<AssetDownload>
  /** The last refusal a gesture on this card met, in the daemon's words. */
  refusal: Ref<string | null>
}

/** Rows a page request asks for at a time. */
export const PAGE_ROWS = 50

export function useCell(options: LiveCellOptions): LiveCellHandle {
  const { session, stream, branch, summary } = options
  const detail = shallowRef<CellDetail | null>(null)
  const previews = ref(new Map<string, PreviewValue>())
  const logs = ref<string | null>(null)
  const rows = ref<ValuePage | null>(null)
  const paging = ref(false)
  const refusal = ref<string | null>(null)
  const showing = ref<CellTabId>('')
  const wantsLogs = ref(false)

  const slug = computed(() => summary.value.slug)
  const flow = () => session.brief.value?.path

  const runId = computed(
    () => session.running.value.find((entry) => entry.slug === slug.value)?.run_id ?? null,
  )
  const streaming = useRunLogs(session, stream, runId)

  // Loads run one after another: a tab change during a refetch would otherwise
  // ask for the same source twice and race over which answer lands.
  let queue: Promise<void> = Promise.resolve()
  // Bumped whenever what was pulled stops describing the cell. An answer that
  // was in flight across that moment describes the cell as it was, and writing
  // it into the cleared caches would leave the previous run's picture standing
  // and the reload — which sees a full cache — skipping the refetch.
  let generation = 0
  // Which output the rows in hand were read out of: a window belongs to one
  // value, and carrying it under another output's tab would show rows nobody
  // asked that output for.
  let paged: string | null = null

  function pull(): void {
    queue = queue.then(load).catch(() => {})
  }

  /**
   * A journal step is as fine-grained as invalidation gets here: a transaction
   * names the branch it touched by id, and this card knows its branch by name.
   * Dropping everything pulled and re-pulling what is on screen costs a read;
   * showing the previous run's preview as if it were this one's does not.
   *
   * The signal is the session's settled revision rather than its live head:
   * a burst of transactions leaves the card in one state, and clearing the
   * caches once per frame in the burst meant every card on screen refetching
   * its source and its preview as many times as the burst was long.
   */
  watch(
    [slug, branch, session.revision],
    () => {
      generation += 1
      detail.value = null
      previews.value = new Map()
      logs.value = null
      rows.value = null
      paged = null
      pull()
    },
    { immediate: true },
  )

  // What is worth fetching depends on the verdict as much as on the tab: a cell
  // the slice reports as materialized has a preview to pull that the same cell
  // reported unmaterialized a moment ago did not. The slice arrives after the
  // transaction that moved it, so the head watcher above does not cover this.
  watch(() => [summary.value.state, summary.value.primary, summary.value.note] as const, pull)

  watch(showing, () => {
    // A window read out of one output says nothing about the next one.
    const shown = shownOutput()
    if (paged !== null && shown !== null && paged !== shown) {
      rows.value = null
      paged = null
    }
    pull()
  })

  async function load(): Promise<void> {
    const here = { slug: slug.value, branch: branch.value, generation }
    if (detail.value === null) {
      const shown = await ask(() =>
        session.request('cells.show', { flow: flow(), branch: here.branch, slug: here.slug }),
      )
      if (shown && current(here)) detail.value = shown
    }
    for (const wanted of wantedOutputs()) {
      if (previews.value.has(wanted)) continue
      const view = await ask(() =>
        session.request('asset.preview', {
          flow: flow(),
          branch: here.branch,
          target: `${here.slug}.${wanted}`,
        }),
      )
      if (view && current(here)) {
        previews.value = new Map(previews.value).set(wanted, previewFrom(view.preview))
      }
    }
    if ((showing.value === 'logs' || wantsLogs.value) && logs.value === null) {
      const captured = await ask(() =>
        session.request('cells.logs', { flow: flow(), branch: here.branch, slug: here.slug }),
      )
      if (captured && current(here)) logs.value = captured.logs ?? ''
    }
  }

  /**
   * Which previews are worth pulling: the one the card opens on — the notebook
   * draws it under the source as well, so it is wanted whatever tab is up — and
   * the one on screen when the reader has moved off it. A branch holding no
   * successful run of this cell has no preview to want.
   */
  function wantedOutputs(): string[] {
    // A note produces nothing the store could have a preview of; its docstring
    // is the whole of it, and asking would be a request the daemon must refuse.
    if (summary.value.note || !observed(summary.value)) return []
    const shown = shownOutput()
    return [...new Set([summary.value.primary, shown].filter((name) => !!name))] as string[]
  }

  function current(here: { slug: string; branch: string; generation: number }): boolean {
    return (
      here.generation === generation && here.slug === slug.value && here.branch === branch.value
    )
  }

  /** The output on screen, when one is — `code` and `logs` are not outputs. */
  function shownOutput(): string | null {
    return showing.value.startsWith('out:') ? showing.value.slice(4) : null
  }

  /**
   * Run a read, keeping its refusal rather than throwing it: a card whose
   * preview the daemon declined still renders everything else it has. Only a
   * failure writes here — a background load landing between a gesture and the
   * caller reading its refusal must not clear the sentence out from under it.
   */
  async function ask<T>(call: () => Promise<T>): Promise<T | null> {
    try {
      return await call()
    } catch (failure) {
      refusal.value = failure instanceof Error ? failure.message : String(failure)
      return null
    }
  }

  /**
   * Reading into the value, which is the gesture that starts a kernel. The
   * window size lives here rather than with the pager: the reader asks for the
   * next rows, and what "next" means is whatever was asked for last time.
   */
  async function readPage(output: string, move: PageMove): Promise<void> {
    refusal.value = null
    const at = rows.value?.offset ?? 0
    const offset =
      move === 'first' ? 0 : move === 'next' ? at + PAGE_ROWS : Math.max(0, at - PAGE_ROWS)
    paging.value = true
    const answer = await ask(() =>
      session.request('asset.page', {
        flow: flow(),
        branch: branch.value,
        target: `${slug.value}.${output}`,
        query: { offset, limit: PAGE_ROWS },
      }),
    )
    paging.value = false
    if (!answer) return
    paged = output
    const { page } = answer
    rows.value = {
      columns: page.columns,
      dtypes: page.dtypes,
      rows: page.rows,
      offset: page.offset,
      totalRows: page.total_rows,
    }
  }

  async function download(output: string): Promise<AssetDownload> {
    return session.request('asset.download', {
      flow: flow(),
      branch: branch.value,
      target: `${slug.value}.${output}`,
    })
  }

  const cell = computed<FlowCell>(() =>
    build({
      summary: summary.value,
      detail: detail.value,
      previews: previews.value,
      logs: logs.value,
      console: streaming.text.value,
      running: runId.value !== null,
      attempts: session.attempts.value[slug.value],
    }),
  )

  return {
    cell,
    base: computed(() => detail.value?.definition_hash ?? null),
    showing,
    runId,
    rows,
    paging,
    readPage,
    readLogs: () => {
      wantsLogs.value = true
      pull()
    },
    download,
    refusal,
  }
}

export interface CellFacts {
  summary: CellSummary
  detail: CellDetail | null
  previews: Map<string, PreviewValue>
  logs: string | null
  console: string
  running: boolean
  /** Runs of this cell this session watched fail before the one standing now. */
  attempts?: number
}

/**
 * The card contract, filled from records. Everything absent stays absent —
 * a cell whose detail has not arrived renders its verdict and its name rather
 * than a placeholder shaped like content.
 *
 * The summary alone is enough for the whole of a card's face except its source
 * and its values, which is why the canvas and the notebook lay out from this
 * too: one definition of what the daemon's records mean, whether a card has
 * pulled its detail yet or not.
 */
export function build(facts: CellFacts): FlowCell {
  const { summary, detail } = facts
  const doc = detail?.doc ?? ''
  return {
    slug: summary.slug,
    doc: doc.split('\n')[0] ?? '',
    consumes: Object.values(summary.consumes),
    params: params(detail),
    source: detail?.source ?? '',
    outputs: outputs(facts, doc),
    primaryOutput: summary.primary ?? undefined,
    status: status(summary, facts.running),
    stale: stale(summary),
    authoredStep: summary.created_step,
    provenance: provenance(detail),
    timing: timing(summary),
    logs: facts.logs ?? undefined,
    console: facts.console ? facts.console.replace(/\n$/, '').split('\n') : undefined,
    error: error(detail, facts.attempts),
    flag: flag(summary),
    externalInput: summary.external || undefined,
    eager: summary.eager || undefined,
    autoDeclined: declined(summary),
    isNote: summary.note,
  }
}

/** A card built from the slice alone — no source, no previews, no logs yet. */
export function summarized(summary: CellSummary, running = false): FlowCell {
  return build({ summary, detail: null, previews: new Map(), logs: null, console: '', running })
}

function status(summary: CellSummary, running: boolean): CellStatus {
  if (running) return 'running'
  switch (summary.state) {
    case 'failed':
      return 'failed'
    case 'unmaterialized':
      return 'unmaterialized'
    case 'unsynced':
      return 'stale'
    default:
      // Current on its own facts but sitting under something that is not. The
      // card carries it as stale and flagged transitive; whether that shows is
      // the view's filter, and dropping it here would make it unfindable.
      return summary.transitive ? 'stale' : 'materialized'
  }
}

/**
 * Causes arrive as sentences, and the chip shows the first one it was given.
 *
 * A transitive verdict is the one case with no sentence of its own: the cell is
 * current on its own facts, and what is not is above it — so the cells the
 * daemon named upstream are the whole of what there is to say.
 */
function stale(summary: CellSummary): StaleInfo | undefined {
  if (summary.state === 'unsynced') {
    return summary.causes.length ? { cause: summary.causes[0] } : undefined
  }
  if (!summary.transitive || summary.upstream.length === 0) return undefined
  return { cause: `upstream ${listed(summary.upstream)} not current`, transitive: true }
}

/**
 * Reactivity's refusal, carried through rather than re-derived.
 *
 * The threshold and the closure's cost both live daemon-side; a card that
 * compared them itself would be the second place the rule is written and the
 * first one to disagree with the scheduler that acts on it.
 */
function declined(summary: CellSummary): AutoDeclinedInfo | undefined {
  if (!summary.auto_declined) return undefined
  return {
    reason: summary.auto_declined.reason,
    estimateSeconds: summary.auto_declined.estimate_seconds,
    untimed: summary.auto_declined.untimed,
  }
}

function listed(slugs: string[]): string {
  const [first, second, ...rest] = slugs
  if (!second) return `\`${first}\` is`
  if (!rest.length) return `\`${first}\` and \`${second}\` are`
  return `\`${first}\`, \`${second}\` and ${rest.length} more are`
}

/** Cost is what a run recorded; a run that recorded none is left without one. */
function timing(summary: CellSummary): TimingInfo | undefined {
  if (summary.cost_seconds === null && !summary.older_env && !summary.reused) return undefined
  return {
    costSeconds: summary.cost_seconds ?? undefined,
    cached: summary.reused || undefined,
    olderEnv: summary.older_env || undefined,
  }
}

function outputs(facts: CellFacts, doc: string): CellOutput[] {
  const { summary, detail } = facts
  // A note declares nothing and runs never: its docstring is the content, and
  // the card shows it as the one thing the cell has.
  if (summary.note) {
    return [
      { name: 'note', declared: 'asset', kind: 'note', preview: { type: 'note', markdown: doc } },
    ]
  }
  const recorded = new Map((detail?.materialized ?? []).map((out) => [out.name, out]))
  return summary.outputs.map((name) => {
    const spec = detail?.produces?.[name]
    const out = recorded.get(name)
    // The slice already says what each output reads as, so the tab strip is
    // badged correctly before this card's detail lands — and identically after.
    const kind = assetKindOf(out?.kind ?? spec?.kind ?? declaredKind(spec) ?? summary.kinds[name])
    return {
      name,
      declared: (spec?.type ?? 'asset') as DeclaredType,
      kind,
      // Waiting for a payload is its own state: an empty grid where one has
      // not landed yet would read as a value with nothing in it.
      preview: facts.previews.get(name) ?? {
        type: 'blocks',
        kind,
        blocks: [],
        pending: observed(summary),
      },
      neverPersisted: persisted(spec, out) ? undefined : true,
    }
  })
}

/** Did this branch see a run of this cell that left something behind? */
function observed(summary: CellSummary): boolean {
  return summary.state === 'synced' || summary.state === 'unsynced'
}

/** A declared `model` is a model on the tab strip before anything has run it. */
function declaredKind(spec: OutputSpec | undefined): string | null {
  return spec && spec.type !== 'asset' ? spec.type : null
}

function persisted(spec: OutputSpec | undefined, out: MaterializedOutput | undefined): boolean {
  if (out) return out.persisted
  return spec ? spec.persist : true
}

function params(detail: CellDetail | null): Record<string, ParamValue> {
  return Object.fromEntries(
    Object.entries(detail?.params ?? {}).map(([name, value]) => [name, value as ParamValue]),
  )
}

/**
 * Authorship, and the flag that says how sure it is. An uncertain window
 * carries the name the store recorded *and* the doubt — dropping either would
 * be the card deciding something the runtime declined to. Before the cell's
 * detail has arrived there is no authorship to show, and a line reading
 * "created user · step 0" would be a claim rather than a wait.
 */
function provenance(detail: CellDetail | null): ProvenanceInfo | undefined {
  const recorded = detail?.provenance
  if (!recorded) return undefined
  return {
    createdBy: actor(recorded.created_by),
    lastEditedBy: actor(recorded.last_edited_by),
    intent: recorded.intent ?? '',
    step: recorded.step,
    attributionUncertain: recorded.attribution_uncertain || undefined,
  }
}

/** `user` is the one reserved actor; every other label is an agent's own. */
function actor(label: string): ActorRef {
  return { kind: label === 'user' ? 'user' : 'agent', label }
}

/**
 * Authorship decides the volume, so the traceback carries who wrote the version
 * that failed: an agent iterating through a broken state is demoted, a person's
 * failure is loud and comes with the handoff.
 */
function error(detail: CellDetail | null, attempts = 0) {
  if (!detail?.error) return undefined
  const author = detail.failed_by ?? detail.author
  return {
    author: (author === 'user' ? 'user' : 'agent') as 'user' | 'agent',
    summary: detail.error.split('\n').filter(Boolean).at(-1) ?? detail.error,
    traceback: detail.error,
    repairedAttempts: attempts || undefined,
  }
}

/**
 * Flags are accepted-but-broken states; the first one is what the chip says.
 *
 * A dangling reference carries its suggestion inside the sentence the daemon
 * wrote — the canonical spelling it would have resolved to. Lifting it back out
 * is what turns the chip into a one-click repair; the sentence stays whole
 * either way, so a flag whose wording this does not recognise still reads.
 */
function flag(summary: CellSummary) {
  const raised = summary.flags[0]
  if (!raised?.detail) return undefined
  const [sentence, suggestion] = split(raised.detail)
  // The code travels with the sentence: the card renders a placeholder name
  // differently from a broken declaration, and only the code tells them apart.
  return { code: raised.code, message: sentence, didYouMean: suggestion }
}

// The sentence lumlflow ends a dangling reference with. It is the runtime's
// wording, not this file's, so it moves when `dsl/normalize.py` moves.
const DID_YOU_MEAN = /\.? did you mean `([^`]+)`\?$/

function split(detail: string): [string, string | undefined] {
  const found = DID_YOU_MEAN.exec(detail)
  if (!found) return [detail, undefined]
  return [detail.slice(0, found.index), found[1]]
}
