import { computed, getCurrentScope, onScopeDispose, ref, shallowRef, watch } from 'vue'
import type { ComputedRef, Ref } from 'vue'

import type { FlowStream } from '@/flow/api/stream'
import type {
  CellDetail,
  CellSummary,
  MaterializedOutput,
  OutputSpec,
  PublishedAsset,
  PublishTarget,
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

export type CellTabId = string

export type PageMove = 'first' | 'next' | 'previous'

export interface LiveCellOptions {
  session: FlowSessionHandle
  stream: FlowStream
  branch: Ref<string>
  summary: Ref<CellSummary>
}

export interface LiveCellHandle {
  cell: ComputedRef<FlowCell>
  base: ComputedRef<string | null>
  detailLoaded: ComputedRef<boolean>
  showing: Ref<CellTabId>
  runId: ComputedRef<string | null>
  rows: Ref<ValuePage | null>
  paging: Ref<boolean>
  readPage: (output: string, move: PageMove) => Promise<void>
  readLogs: () => void
  downloadUrl: (output: string) => string
  publish: (output: string, target: PublishTarget) => Promise<PublishedAsset>
  refusal: Ref<string | null>
}

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
  const refreshing = ref(false)

  const slug = computed(() => summary.value.slug)
  const flow = () => session.brief.value?.path

  const runId = computed(
    () => session.running.value.find((entry) => entry.slug === slug.value)?.run_id ?? null,
  )
  const streaming = useRunLogs(session, stream, runId)

  const stopState = session.onState((frame) => {
    if (
      frame.state === 'refreshing' &&
      frame.lane === branch.value &&
      frame.cell === slug.value &&
      runId.value === null
    ) {
      refreshing.value = true
    }
  })
  if (getCurrentScope()) onScopeDispose(stopState)

  watch([slug, branch], () => {
    refreshing.value = false
  })
  watch(runId, (id) => {
    if (id !== null) refreshing.value = false
  })
  watch(
    () => summary.value.auto_declined?.reason,
    (reason) => {
      if (reason === 'refresh-failed') refreshing.value = false
    },
  )

  // Loads run one after another: a tab change during a refetch would otherwise
  // ask for the same source twice and race over which answer lands.
  let queue: Promise<void> = Promise.resolve()
  let generation = 0
  let detailGeneration = -1
  let detailSlug: string | null = null
  let detailBranch: string | null = null
  let paged: string | null = null

  function pull(): void {
    queue = queue.then(load).catch(() => {})
  }

  watch(
    [slug, branch, session.revision],
    ([nextSlug, nextBranch]) => {
      generation += 1
      detailGeneration = -1
      if (nextSlug !== detailSlug || nextBranch !== detailBranch) detail.value = null
      detailSlug = nextSlug
      detailBranch = nextBranch
      previews.value = new Map()
      logs.value = null
      rows.value = null
      paged = null
      pull()
    },
    { immediate: true },
  )

  watch(() => [summary.value.state, summary.value.primary, summary.value.note] as const, pull)

  watch(
    () => summary.value.tracker?.state,
    () => {
      generation += 1
      detailGeneration = -1
      previews.value = new Map()
      pull()
    },
  )

  watch(showing, () => {
    const shown = shownOutput()
    if (paged !== null && shown !== null && paged !== shown) {
      rows.value = null
      paged = null
    }
    pull()
  })

  async function load(): Promise<void> {
    const here = { slug: slug.value, branch: branch.value, generation }
    if (detailGeneration !== here.generation) {
      const shown = await ask(() =>
        session.request('cells.show', { flow: flow(), branch: here.branch, slug: here.slug }),
      )
      if (shown && current(here)) {
        detail.value = shown
        detailGeneration = here.generation
      }
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
        previews.value = new Map(previews.value).set(
          wanted,
          previewFrom(view.preview, { runName: view.slug, tracker: view.tracker }),
        )
      }
    }
    if ((showing.value === 'logs' || wantsLogs.value) && logs.value === null) {
      const captured = await ask(() =>
        session.request('cells.logs', { flow: flow(), branch: here.branch, slug: here.slug }),
      )
      if (captured && current(here)) logs.value = captured.logs ?? ''
    }
  }

  function wantedOutputs(): string[] {
    if (summary.value.note || !observed(summary.value)) return []
    const shown = shownOutput()
    return [...new Set([summary.value.primary, shown].filter((name) => !!name))] as string[]
  }

  function current(here: { slug: string; branch: string; generation: number }): boolean {
    return (
      here.generation === generation && here.slug === slug.value && here.branch === branch.value
    )
  }

  function shownOutput(): string | null {
    return showing.value.startsWith('out:') ? showing.value.slice(4) : null
  }

  async function ask<T>(call: () => Promise<T>): Promise<T | null> {
    try {
      return await call()
    } catch (failure) {
      refusal.value = failure instanceof Error ? failure.message : String(failure)
      return null
    }
  }

  async function readPage(output: string, move: PageMove): Promise<void> {
    refusal.value = null
    const at = paged === output ? rows.value?.offset : undefined
    const offset =
      move === 'first' || at === undefined
        ? 0
        : move === 'next'
          ? at + PAGE_ROWS
          : Math.max(0, at - PAGE_ROWS)
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
      totalColumns: page.total_columns,
    }
  }

  function downloadUrl(output: string): string {
    return session.downloadUrl(branch.value, `${slug.value}.${output}`)
  }

  function publish(output: string, target: PublishTarget): Promise<PublishedAsset> {
    return session.request('asset.publish', {
      flow: flow(),
      branch: branch.value,
      target: `${slug.value}.${output}`,
      ...target,
    })
  }

  const cell = computed<FlowCell>(() => {
    const built = build({
      summary: summary.value,
      detail: detail.value,
      previews: previews.value,
      logs: logs.value,
      console: streaming.text.value,
      running: runId.value !== null,
      refreshing: refreshing.value,
      attempts: session.attempts.value[slug.value],
    })
    return {
      ...built,
      outputs: built.outputs.map((output) => ({
        ...output,
        downloadUrl:
          output.kind === 'experiment' || output.neverPersisted
            ? undefined
            : downloadUrl(output.name),
      })),
    }
  })

  return {
    cell,
    base: computed(() => detail.value?.definition_hash ?? null),
    detailLoaded: computed(() => detail.value !== null),
    showing,
    runId,
    rows,
    paging,
    readPage,
    readLogs: () => {
      wantsLogs.value = true
      pull()
    },
    downloadUrl,
    publish,
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
  refreshing?: boolean
  attempts?: number
}

export function build(facts: CellFacts): FlowCell {
  const { summary, detail } = facts
  const doc = detail?.doc ?? ''
  return {
    uid: summary.uid,
    slug: summary.slug,
    doc: doc.split('\n')[0] ?? '',
    consumes: Object.values(summary.consumes),
    consumesByInput: summary.consumes,
    params: params(detail),
    source: detail?.source ?? '',
    outputs: outputs(facts, doc),
    primaryOutput: summary.primary ?? undefined,
    status: status(summary, facts.running, facts.refreshing ?? false),
    stale: stale(summary),
    authoredStep: summary.created_step,
    order: summary.order,
    provenance: provenance(detail),
    timing: timing(summary),
    logs: facts.logs ?? undefined,
    console: facts.console ? facts.console.replace(/\n$/, '').split('\n') : undefined,
    error: error(detail, facts.attempts),
    flag: flag(summary),
    externalInput: summary.external || undefined,
    eager: summary.eager || undefined,
    autoDeclined: declined(summary),
    tracker: summary.tracker ?? detail?.tracker ?? undefined,
    sdkVersionWarning: detail?.sdk_version_warning ?? undefined,
    isNote: summary.note,
  }
}

export function summarized(summary: CellSummary, running = false): FlowCell {
  return build({ summary, detail: null, previews: new Map(), logs: null, console: '', running })
}

function status(summary: CellSummary, running: boolean, refreshing: boolean): CellStatus {
  if (running) return 'running'
  if (refreshing) return 'refreshing'
  switch (summary.state) {
    case 'failed':
      return 'failed'
    case 'unmaterialized':
      return 'unmaterialized'
    case 'unsynced':
      return 'stale'
    default:
      return summary.transitive ? 'stale' : 'materialized'
  }
}

function stale(summary: CellSummary): StaleInfo | undefined {
  if (summary.state === 'unsynced') {
    return summary.causes.length ? { cause: summary.causes[0] } : undefined
  }
  if (!summary.transitive || summary.upstream.length === 0) return undefined
  return { cause: `upstream ${listed(summary.upstream)} not current`, transitive: true }
}

function declined(summary: CellSummary): AutoDeclinedInfo | undefined {
  if (!summary.auto_declined) return undefined
  return {
    reason: summary.auto_declined.reason,
    estimateSeconds: summary.auto_declined.estimate_seconds,
    untimed: summary.auto_declined.untimed,
    detail: summary.auto_declined.detail,
  }
}

function listed(slugs: string[]): string {
  const [first, second, ...rest] = slugs
  if (!second) return `\`${first}\` is`
  if (!rest.length) return `\`${first}\` and \`${second}\` are`
  return `\`${first}\`, \`${second}\` and ${rest.length} more are`
}

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
  if (summary.note) {
    return [
      { name: 'note', declared: 'asset', kind: 'note', preview: { type: 'note', markdown: doc } },
    ]
  }
  const recorded = new Map((detail?.materialized ?? []).map((out) => [out.name, out]))
  return summary.outputs.map((name) => {
    const spec = detail?.produces?.[name]
    const out = recorded.get(name)
    const kind = assetKindOf(out?.kind ?? spec?.kind ?? declaredKind(spec) ?? summary.kinds[name])
    return {
      name,
      declared: (spec?.type ?? 'asset') as DeclaredType,
      kind,
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

function observed(summary: CellSummary): boolean {
  return summary.state === 'synced' || summary.state === 'unsynced'
}

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

function actor(label: string): ActorRef {
  return { kind: label === 'user' ? 'user' : 'agent', label }
}

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

function flag(summary: CellSummary) {
  const raised = summary.flags[0]
  if (!raised?.detail) return undefined
  const [sentence, suggestion] = split(raised.detail)
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
