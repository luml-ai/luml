<template>
  <div class="flex h-full min-h-0 flex-col gap-3">
    <SessionBanners
      :degraded="session.degraded.value"
      :changes-behind="session.changesBehind.value"
      @open-catchup="onOpenActivity"
    />

    <WorkbenchTopBar
      v-model:view="selection.view.value"
      v-model:show-tint="showTint"
      :session="records.overview.value"
      :viewed-branch="viewedBranch"
      :branches="records.branches.value"
      :branch-preflight="branchClosure"
      :runnable="leaves.length > 0"
      :ops-disabled="!session.reachable.value"
      :stale="staleCounts"
      @open-catchup="onOpenActivity"
      @branch-preflight="onBranchPreflight"
      @rerun-branch="onRerunBranch"
      @stop-session="onStop"
      @view-branch="onViewBranch"
      @checkout-branch="onCheckout"
      @new-branch="onNewBranch"
    />

    <div class="flex min-h-0 flex-1 gap-3">
      <aside
        class="w-80 shrink-0 min-h-0 overflow-hidden rounded-lg border border-surface-200 dark:border-surface-700"
      >
        <LeftPanel
          v-model:open="panelOpen"
          :branches="records.branches.value"
          :cells="cells"
          :viewed-branch="viewedBranch"
          :session="records.overview.value"
          :env="records.env.value"
          :settings="records.settings.value"
          :journal="records.journal.value"
          :behind="openedBehind"
          :branch-busy="branchBusy"
          :agents="agents"
          :agents-loading="agentsLoading"
          :agents-error="agentsError"
          :agents-busy="agentBusyIds"
          @open-graph="graphVisible = true"
          @new-branch="onNewBranch"
          @rewind="onRewind"
          @checkpoint="onCheckpoint"
          @pair="onPair"
          @open-agents="onOpenAgents"
          @setup-agents="onSetupAgents"
          @update-agent="onUpdateAgent"
          @remove-agent="onRemoveAgent"
          @select-cell="onSelect"
          @update-settings="onUpdateSettings"
          @restart-kernel="onRestartKernel"
        />
      </aside>

      <main class="flex min-h-0 min-w-0 flex-1 flex-col gap-3">
        <p v-if="slice.error.value" class="px-1 text-base text-(--p-message-error-color)">
          {{ slice.error.value }}
        </p>

        <KernelDeathBanner
          v-if="kernelDeath"
          :slug="kernelDeath.slug"
          :cause="kernelDeath.cause"
          @restart-kernel="onRestartAfterDeath"
        />

        <div class="flex items-center gap-2">
          <Button text label="add a cell" :disabled="!session.reachable.value" @click="onAddCell()">
            <template #icon><Plus :size="14" /></template>
          </Button>
          <Button
            text
            severity="secondary"
            :label="scratchOpen ? 'hide scratch' : 'scratch'"
            @click="scratchOpen = !scratchOpen"
          >
            <template #icon><Terminal :size="14" /></template>
          </Button>
        </div>

        <ReplPanel
          v-if="scratchOpen"
          :branch="viewedBranch"
          :disabled="!session.reachable.value"
          :evaluate="ops.evaluate"
        />

        <div class="min-h-0 flex-1">
          <!-- A branch still being read is not a branch with nothing on it. -->
          <p v-if="slice.loading.value && !cells.length" class="px-1 text-base text-muted-color">
            reading the lane…
          </p>
          <EmptyFlowState
            v-else-if="!cells.length"
            :paired="records.overview.value.paired"
            @notebook="selection.view.value = 'notebook'"
            @cheatsheet="onCheatsheet"
            @create="onAddCell()"
            @pair="onPair"
          />
          <FlowCanvas
            v-else-if="selection.view.value === 'canvas'"
            v-model:state="canvasState"
            class="h-full rounded-lg border border-surface-200 dark:border-surface-700"
            :cells="cells"
            :branch="viewedBranch"
            :selected-slug="selection.selectedSlug.value"
            :tinted-slugs="tintedSlugs"
            :preflights="{}"
            @select="onSelect"
          >
            <template #card="{ cell, selected }">
              <LiveCellCard
                v-bind="cardProps(cell.slug, selected, 'canvas')"
                v-on="cardEvents(cell.slug)"
              />
              <AgentEndedBanner
                v-if="endedUnder === cell.slug"
                :cell="cell"
                :failed-run="Boolean(failedCell)"
                :unsynced-assets="endedUnsynced.length"
                class="mt-2"
              />
            </template>
          </FlowCanvas>
          <NotebookColumn
            v-else
            :cells="cells"
            :branch="viewedBranch"
            :selected-slug="selection.selectedSlug.value"
            :tinted-slugs="tintedSlugs"
            :preflights="{}"
            @select="onSelect"
          >
            <template #card="{ cell, selected }">
              <LiveCellCard
                v-bind="cardProps(cell.slug, selected, 'notebook')"
                v-on="cardEvents(cell.slug)"
              />
              <AgentEndedBanner
                v-if="endedUnder === cell.slug"
                :cell="cell"
                :failed-run="Boolean(failedCell)"
                :unsynced-assets="endedUnsynced.length"
                class="mt-2"
              />
            </template>
          </NotebookColumn>
        </div>

        <Dialog v-model:visible="renaming" modal header="Rename cell" :style="{ width: '24rem' }">
          <div class="flex flex-col gap-3">
            <p class="text-sm text-muted-color">
              free. consumers rewire under the same identity. nothing recomputes.
            </p>
            <InputText v-model="renameTo" aria-label="new name" @keyup.enter="onRenameConfirm" />
            <div class="flex justify-end gap-2">
              <Button text severity="secondary" label="cancel" @click="renaming = false" />
              <Button label="rename" @click="onRenameConfirm" />
            </div>
          </div>
        </Dialog>
      </main>
    </div>

    <NewBranchDialog
      v-model:visible="forking"
      :from="viewedBranch"
      :refusal="forkRefusal"
      :busy="branchBusy"
      @create="onFork"
    />

    <FromHereDialog
      v-model:visible="fromHereOpen"
      :branch="fromHere?.branch ?? viewedBranch"
      :head-step="fromHere?.head ?? 0"
      :newest-step="fromHere?.newest ?? 0"
      :refusal="fromHereRefusal"
      :busy="branchBusy"
      @new-lane="onLaneFromHere"
      @continue="settleFromHere(fromHere?.branch ?? null)"
    />

    <BranchGraphOverlay
      v-model:visible="graphVisible"
      :branches="records.branches.value"
      selectable
      @view="onViewBranch"
      @checkout="onCheckout"
      @archive="onArchive"
      @compare="onCompare"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onScopeDispose, provide, ref, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button, Dialog, InputText } from 'primevue'
import { useToast } from 'primevue/usetoast'
import { Plus, Terminal } from 'lucide-vue-next'

import { FlowApiError } from '@/flow/api/client'
import type { FlowStream } from '@/flow/api/stream'
import type { AgentHarness, CellSummary } from '@/flow/api/types'
import FromHereDialog from '../components/branch/FromHereDialog.vue'
import NewBranchDialog from '../components/branch/NewBranchDialog.vue'
import FlowCanvas, { type CanvasSessionState } from '../components/canvas/FlowCanvas.vue'
import AgentEndedBanner from '../components/card/AgentEndedBanner.vue'
import KernelDeathBanner from '../components/card/KernelDeathBanner.vue'
import LiveCellCard from '../components/card/LiveCellCard.vue'
import BranchGraphOverlay from '../components/graph/BranchGraphOverlay.vue'
import LeftPanel from '../components/panel/LeftPanel.vue'
import ReplPanel from '../components/repl/ReplPanel.vue'
import SessionBanners from '../components/session/SessionBanners.vue'
import { coalesceTransactions } from '../live/toasts'
import { formatCount } from '../model/format'
import { reorderNeighbours } from '../model/registry'
import { summarized } from '../live/useCell'
import { MOVE_GUARD, MoveCancelled, useFlowOps } from '../live/useFlowOps'
import type { FlowSessionHandle } from '../live/useFlowSession'
import { useSelection } from '../live/useSelection'
import { useSlice } from '../live/useSlice'
import { settingsReport, useWorkbench } from '../live/useWorkbench'
import type { FlowSettings, Preflight, StaleCounts } from '../model/types'
import EmptyFlowState from './EmptyFlowState.vue'
import NotebookColumn from './NotebookColumn.vue'
import WorkbenchTopBar from './WorkbenchTopBar.vue'

/**
 * The workbench on a live session: one screen, two views over the same branch
 * slice and the same cards.
 *
 * Which branch is **viewed** is this screen's own state and costs nothing —
 * reading another branch is a store read, no lock and no kernel — while
 * checking one out rebinds the single worktree and is the one gesture here
 * that touches files. The left panel, both views and the URL all re-scope
 * together, because a panel describing one branch beside a canvas drawing
 * another is worse than either alone.
 */
const props = defineProps<{
  session: FlowSessionHandle
  stream: FlowStream
}>()

const route = useRoute()
const router = useRouter()
const toast = useToast()

const session = props.session
const ops = useFlowOps(session, { guard: askWhereFrom })
const records = useWorkbench(session)

const selection = useSelection(route, {
  defaultBranch: computed(() => session.brief.value?.branch ?? 'main'),
})

const viewedBranch = computed(() => selection.viewedBranch.value)
const slice = useSlice(session, viewedBranch)
const canvasState = shallowRef<CanvasSessionState | null>(null)

// --- the transitive filter --------------------------------------------------

const showTint = ref(false)

// The direct view is what a cell's own facts say; these three states are its
// members and are counted apart, because "stale" is a claim against a baseline
// and one of them has no baseline to make it against.
const unsynced = computed(() => slice.direct.value.filter((cell) => cell.state === 'unsynced'))
const unmaterialized = computed(() =>
  slice.direct.value.filter((cell) => cell.state === 'unmaterialized'),
)
const transitive = computed(() => slice.transitive.value)

/**
 * With the filter off, a transitively stale cell renders as what it is on its
 * own facts — current — and the header count above is what keeps it findable.
 * The filter is applied to the summary the card renders rather than to the
 * chip, so the two views and the panel cannot disagree about it.
 */
const shown = computed<CellSummary[]>(() =>
  slice.cells.value.map((cell) =>
    cell.transitive && !showTint.value ? { ...cell, transitive: false, upstream: [] } : cell,
  ),
)

const shownBySlug = computed(() => new Map(shown.value.map((cell) => [cell.slug, cell])))

const running = computed(() => new Set(session.running.value.map((entry) => entry.slug)))

/** The slice as cards: what the two views lay out and the panel lists. */
const cells = computed(() =>
  shown.value.map((summary) => summarized(summary, running.value.has(summary.slug))),
)

const moveNeighbours = computed(() => reorderNeighbours(cells.value))

const tintedSlugs = computed(
  () => new Set(showTint.value ? transitive.value.map((cell) => cell.slug) : []),
)

/**
 * The counts the bar states, and the first cause behind them. The cause is the
 * daemon's own sentence off the first unsynced cell — naming *which* cells is
 * the panel's job and the cards', and repeating it here was the fourth channel.
 */
const staleCounts = computed<StaleCounts | undefined>(() => {
  const counts = {
    unsynced: unsynced.value.length,
    downstream: transitive.value.length,
    unmaterialized: unmaterialized.value.length,
    waitingOnThreshold: 0,
    neverTimed: 0,
    blockedByFailure: 0,
    refreshFailed: 0,
    cause: unsynced.value[0]?.causes[0],
  }
  for (const cell of slice.cells.value) {
    switch (cell.auto_declined?.reason) {
      case 'too-expensive':
        counts.waitingOnThreshold += 1
        break
      case 'never-timed':
        if (cell.state !== 'unmaterialized') counts.neverTimed += 1
        break
      case 'blocked':
        counts.blockedByFailure += 1
        break
      case 'refresh-failed':
        counts.refreshFailed += 1
        break
    }
  }
  const total =
    counts.unsynced +
    counts.downstream +
    counts.unmaterialized +
    counts.waitingOnThreshold +
    counts.neverTimed +
    counts.blockedByFailure +
    counts.refreshFailed
  return total > 0 ? counts : undefined
})

// --- selection and cross-navigation -----------------------------------------

function onSelect(slug: string): void {
  if (selection.selectedSlug.value === slug) return
  selection.selectedSlug.value = slug
}

// A branch that does not carry the selected cell cannot keep pointing at it.
watch(shownBySlug, (bySlug) => {
  const slug = selection.selectedSlug.value
  if (slug && bySlug.size > 0 && !bySlug.has(slug)) selection.selectedSlug.value = null
})

// --- the cards --------------------------------------------------------------

/**
 * The card is the same one in both views, bound the same way — spelling the
 * bindings out twice is how the two densities start to differ by accident.
 */
function cardProps(slug: string, selected: boolean, density: 'canvas' | 'notebook') {
  const moves = moveNeighbours.value.get(slug)
  return {
    session,
    stream: props.stream,
    branch: viewedBranch.value,
    summary: shownBySlug.value.get(slug)!,
    density,
    selected,
    // Other branches waiting on this cell's run: what makes stop read as
    // leaving rather than as cancelling.
    awaiters: Math.max(0, (inFlight.value.get(slug)?.awaiting ?? 1) - 1),
    renamedFrom: justRenamed.value.get(slug),
    canMoveUp: moves !== undefined && moves.up !== null,
    canMoveDown: moves !== undefined && moves.down !== null,
  }
}

/**
 * A rename that just landed, so the card can say it is the same cell under a
 * new name. Only the newest transaction is read: an agent's `mv` arrives as a
 * `renamed` op, and the next thing that happens is what retires the note.
 */
const justRenamed = computed(() => {
  const latest = session.transactions.value.at(-1)
  return new Map(
    (latest?.ops ?? []).filter((op) => op.op === 'renamed').map((op) => [op.new_slug, op.old_slug]),
  )
})

function cardEvents(slug: string) {
  return {
    run: (payload: { force: boolean }) => void onRun(slug, payload),
    stop: onStop,
    rename: () => onRename(slug),
    duplicate: () => void onDuplicate(slug),
    'add-downstream': () => void onAddCell(slug),
    'move-up': () => void onMove(slug, 'up'),
    'move-down': () => void onMove(slug, 'down'),
    'view-branch': onViewBranch,
  }
}

const inFlight = computed(() => new Map(session.running.value.map((run) => [run.slug, run])))

/**
 * How far behind the reader was when they attached. The panel's feed draws its
 * divider here; read live it would be zero by the time the section painted,
 * because opening the section is what marks the window seen.
 */
const openedBehind = ref(session.changesBehind.value)

watch(session.changesBehind, (count) => {
  if (count > openedBehind.value) openedBehind.value = count
})

// --- ops --------------------------------------------------------------------

const graphVisible = ref(false)

/** Which panel sections are open — the catch-up marker's destination. */
const panelOpen = ref<string[]>(['cells'])
const scratchOpen = ref(false)
const renaming = ref(false)
const renameFrom = ref('')
const renameTo = ref('')
const branchClosure = ref<Preflight | null>(null)
/** Bumped whenever the branch closure in hand stops describing this branch. */
let plans = 0
const kernelDeath = ref<{ slug: string; cause?: string } | null>(null)

function refused(failure: unknown): void {
  // Stepping back from a gesture is not something lumlflow refused.
  if (failure instanceof MoveCancelled) return
  toast.add({
    severity: 'warn',
    summary: 'lumlflow refused this',
    detail: failure instanceof Error ? failure.message : String(failure),
    life: 4000,
  })
}

function acknowledge(summary: string, detail: string): void {
  toast.add({ severity: 'secondary', summary, detail, life: 4000 })
}

/**
 * A run, and the one failure that is not the cell's: a kernel that died takes
 * the queue with it and is a banner rather than a traceback, because nothing
 * about the cell explains it.
 */
async function onRun(slug: string, payload: { force: boolean }): Promise<void> {
  try {
    await ops.run(slug, { branch: viewedBranch.value, force: payload.force })
  } catch (failure) {
    if (failure instanceof FlowApiError && failure.kind === 'KernelError') {
      kernelDeath.value = { slug, cause: failure.message }
      return
    }
    refused(failure)
  }
}

/**
 * Stop is honest about its scope twice over: it stops the run only when this
 * branch was the last one waiting on it, and it never claims to have stopped
 * the agent — that process is not ours.
 */
async function onStop(): Promise<void> {
  try {
    const left = await ops.cancel(viewedBranch.value)
    if (!left.left) return
    acknowledge(
      left.stopped ? 'Run stopped' : `${viewedBranch.value} left the run`,
      left.stopped
        ? 'the queue is drained. stop the agent in its own terminal (Ctrl+C).'
        : `it keeps going for ${left.awaiting} other lane${left.awaiting === 1 ? '' : 's'}`,
    )
  } catch (failure) {
    refused(failure)
  }
}

// --- editing ----------------------------------------------------------------

async function onAddCell(after?: string): Promise<void> {
  try {
    const anchor = after ?? selection.selectedSlug.value ?? undefined
    const added = await ops.addCell({ branch: viewedBranch.value, after, anchor })
    selection.selectedSlug.value = added.slug
    acknowledge(
      `Added ${added.slug}`,
      after ? `consumes ${after}. name it and write its materialize.` : 'name it and write it',
    )
  } catch (failure) {
    refused(failure)
  }
}

async function onMove(slug: string, direction: 'up' | 'down'): Promise<void> {
  const neighbour = moveNeighbours.value.get(slug)?.[direction]
  if (!neighbour) return
  try {
    const moved = await ops.reorder(slug, {
      branch: viewedBranch.value,
      ...(direction === 'up' ? { before: neighbour } : { after: neighbour }),
    })
    slice.applyOrder(moved.slug, moved.order)
  } catch (failure) {
    refused(failure)
  }
}

/** Duplicating carries the source and its inputs across under a new identity. */
async function onDuplicate(slug: string): Promise<void> {
  try {
    // The slice carries no source — only a card's detail does — so the body is
    // read here. Without it the copy would be a blank scaffold, which is the
    // one thing a duplicate must not be.
    const original = await session.request('cells.show', {
      flow: session.brief.value?.path,
      branch: viewedBranch.value,
      slug,
    })
    const copy = await ops.addCell({
      branch: viewedBranch.value,
      slug: `${slug}_copy`,
      source: original.source,
    })
    selection.selectedSlug.value = copy.slug
    acknowledge(`Duplicated as ${copy.slug}`, "keeps the original's inputs")
  } catch (failure) {
    refused(failure)
  }
}

function onRename(slug: string): void {
  renameFrom.value = slug
  renameTo.value = slug
  renaming.value = true
}

async function onRenameConfirm(): Promise<void> {
  const to = renameTo.value.trim().toLowerCase()
  renaming.value = false
  if (!to || to === renameFrom.value) return
  try {
    const renamed = await ops.rename(renameFrom.value, to, { branch: viewedBranch.value })
    selection.selectedSlug.value = to
    acknowledge(
      `Renamed to ${to}`,
      renamed.rewired.length
        ? `${renamed.rewired.join(', ')} rewired. nothing recomputes.`
        : 'nothing recomputes. references hold the identity, not the name.',
    )
  } catch (failure) {
    refused(failure)
  }
}

// --- run controls over the whole branch --------------------------------------

/** Cells nothing else on this branch consumes — where rerunning a branch ends. */
const leaves = computed(() => {
  const consumed = new Set(
    cells.value.flatMap((cell) => cell.consumes.map((ref) => ref.split('.')[0])),
  )
  return cells.value.filter((cell) => !cell.isNote && !consumed.has(cell.slug)).map((c) => c.slug)
})

async function onBranchPreflight(): Promise<void> {
  if (!leaves.value.length) return
  const asked = plans
  try {
    const answer = await ops.preflight(leaves.value, viewedBranch.value)
    // The answer describes the branch as it was when it was asked for. Landing
    // it after a switch would quote one branch's cost over another's leaves.
    if (asked !== plans) return
    branchClosure.value = {
      cached: answer.cached,
      recompute: answer.recompute,
      unknown: answer.unknown,
      totalSeconds: answer.estimate_seconds,
      reasons: answer.reasons ?? [],
    }
  } catch (failure) {
    refused(failure)
  }
}

async function onRerunBranch(payload: { force: boolean }): Promise<void> {
  try {
    await ops.run(undefined, { branch: viewedBranch.value, force: payload.force })
  } catch (failure) {
    refused(failure)
  }
}

const agents = ref<AgentHarness[]>([])
const agentsLoading = ref(false)
const agentsError = ref<string | null>(null)
const agentBusy = ref<Set<string>>(new Set())
const agentBusyIds = computed(() => [...agentBusy.value])
let agentRead = 0

function onPair(): void {
  if (!panelOpen.value.includes('agents')) {
    panelOpen.value = [...panelOpen.value, 'agents']
    return
  }
  void onOpenAgents()
}

async function onOpenAgents(): Promise<void> {
  const read = ++agentRead
  agentsLoading.value = true
  agentsError.value = null
  try {
    const answer = await session.request('agents.harnesses', {})
    if (read === agentRead) agents.value = answer.harnesses
  } catch (failure) {
    if (read === agentRead) {
      agentsError.value = failure instanceof Error ? failure.message : String(failure)
    }
  } finally {
    if (read === agentRead) agentsLoading.value = false
  }
}

function setAgentBusy(id: string, busy: boolean): void {
  const next = new Set(agentBusy.value)
  if (busy) next.add(id)
  else next.delete(id)
  agentBusy.value = next
}

function applyHarness(next: AgentHarness): void {
  const at = agents.value.findIndex((harness) => harness.id === next.id)
  if (at < 0) {
    agents.value = [...agents.value, next]
    return
  }
  agents.value = agents.value.map((harness, index) => (index === at ? next : harness))
}

async function setupAgent(id: string, consent: boolean): Promise<void> {
  setAgentBusy(id, true)
  try {
    applyHarness(await session.request('agents.setup', { harness: id, consent }))
  } catch (failure) {
    refused(failure)
  } finally {
    setAgentBusy(id, false)
  }
}

async function onSetupAgents(ids: string[], consent: boolean): Promise<void> {
  for (const id of ids) await setupAgent(id, consent)
}

function onUpdateAgent(id: string): void {
  void setupAgent(id, false)
}

async function onRemoveAgent(id: string): Promise<void> {
  setAgentBusy(id, true)
  try {
    applyHarness(await session.request('agents.remove', { harness: id }))
  } catch (failure) {
    refused(failure)
  } finally {
    setAgentBusy(id, false)
  }
}

/**
 * The catch-up marker's destination: the panel's activity section, which is the
 * journal's one home. Opening it is what marks the window seen — the count is
 * about what the reader has not looked at, and the feed is looking at it.
 */
function onOpenActivity(): void {
  if (!panelOpen.value.includes('activity')) panelOpen.value = [...panelOpen.value, 'activity']
  session.markSeen()
}

async function onRestartAfterDeath(): Promise<void> {
  kernelDeath.value = null
  await onRestartKernel()
}

// A closure computed against a branch that has since moved is a plan for a
// different flow; it is re-asked for when the popover next opens.
watch([viewedBranch, () => session.head.value], () => {
  branchClosure.value = null
  plans += 1
})

// --- what the journal announces ----------------------------------------------

/**
 * Transactions become toasts, coalesced by intent and demoted by authorship.
 *
 * Only what arrived since the last pass is announced: re-toasting the window
 * the session keeps would replay an agent's whole morning on every reconnect.
 *
 * Announcing starts at the catch-up. Subscribing replays the journal from the
 * client's cursor — the whole of it on a first load — and that window is
 * history, counted by the catch-up marker. Toasting it would greet a reopened
 * workbench with an inbox, including red failure toasts for runs that failed
 * yesterday.
 */
let announced: number | null = null

const stopWatchingReplay = props.stream.onFrame((frame) => {
  if (!('channel' in frame) || frame.channel !== 'journal') return
  if (frame.type !== 'caught_up' || frame.flow !== session.path.value) return
  if (announced === null) announced = frame.step
})

const stopRearmingReplay = props.stream.onStatus((status) => {
  if (status === 'connecting') announced = null
})

onScopeDispose(() => {
  stopWatchingReplay()
  stopRearmingReplay()
})

watch(
  () => session.transactions.value,
  (entries) => {
    if (announced === null) return
    const fresh = entries.filter((entry) => entry.step > announced!)
    if (!fresh.length) return
    announced = Math.max(announced, ...fresh.map((entry) => entry.step))
    for (const plan of coalesceTransactions(fresh)) {
      toast.add({
        severity: plan.severity,
        summary: plan.summary,
        detail: plan.detail,
        life: plan.severity === 'error' ? 8000 : 4000,
      })
    }
  },
)

// --- the agent that stopped --------------------------------------------------

/**
 * A session that ended leaving something outstanding is a state, not an event:
 * the banner stays until the outstanding thing is dealt with. What it never
 * does is say why the agent stopped — a clean `agent_end` and a killed process
 * look the same from here, and only one of them is journaled.
 */
const latestAgentEnd = computed(() => {
  let latest: number | null = null
  for (const entry of session.transactions.value) {
    if (entry.ops.some((op) => op.op === 'agent_end')) latest = entry.step
  }
  return latest
})

function changedBeforeAgentEnded(cell: CellSummary | undefined): boolean {
  return (
    cell !== undefined && latestAgentEnd.value !== null && cell.changed_step < latestAgentEnd.value
  )
}

const endedUnsynced = computed(() => unsynced.value.filter(changedBeforeAgentEnded))
const failedCell = computed(() =>
  cells.value.find(
    (cell) => cell.status === 'failed' && changedBeforeAgentEnded(shownBySlug.value.get(cell.slug)),
  ),
)
const agentEnded = computed(
  () =>
    !session.agent.value &&
    latestAgentEnd.value !== null &&
    (failedCell.value !== undefined || endedUnsynced.value.length > 0),
)

/** The banner hangs under the cell the trouble is about, not over the screen. */
const endedUnder = computed(() => {
  if (!agentEnded.value) return null
  if (failedCell.value) return failedCell.value.slug
  return endedUnsynced.value.at(-1)?.slug ?? null
})

/** Viewing is free; this is the read that scopes the whole screen. */
function onViewBranch(name: string): void {
  selection.viewedBranch.value = name
  graphVisible.value = false
}

// --- moving between branches, and within one ---------------------------------

const forking = ref(false)
const forkRefusal = ref<string | null>(null)

/**
 * One op at a time across all three verbs. Forking, rewinding and marking all
 * land as transactions on the same branch, and a second one launched over the
 * first would be a gesture aimed at a branch that has already moved.
 */
const branchBusy = ref(false)

function onNewBranch(): void {
  forkRefusal.value = null
  forking.value = true
}

/**
 * A fork off the viewed branch at its head, and then the new branch is what
 * this screen reads. Landing anywhere else would mint a branch and leave the
 * user looking at the one they forked from, with nothing to say which is which.
 */
async function onFork(name: string): Promise<void> {
  if (branchBusy.value) return
  branchBusy.value = true
  forkRefusal.value = null
  const from = viewedBranch.value
  try {
    const created = await ops.fork(name, from)
    forking.value = false
    selection.viewedBranch.value = created.branch
    acknowledge(
      `Started ${created.branch}`,
      `from ${from} · ${formatCount(created.cells, 'cell')}. no file and no value is copied.`,
    )
  } catch (failure) {
    // Named in the dialog rather than in a toast: a name already taken is
    // about the field the user is still standing in.
    forkRefusal.value = failure instanceof Error ? failure.message : String(failure)
  } finally {
    branchBusy.value = false
  }
}

/**
 * Rewind moves the branch to a step and restores the selection it had there.
 * Nothing recomputes, nothing is lost and no step is added — the steps after
 * it stay in the journal, which is what makes moving forward again the same
 * gesture. The branch stands there until the next change on it.
 */
async function onRewind(step: number): Promise<void> {
  if (branchBusy.value) return
  branchBusy.value = true
  const branch = viewedBranch.value
  try {
    const restored = await ops.rewind(step, { branch })
    acknowledge(
      `${branch} stands at step ${step}`,
      `${formatCount(restored.projected?.written.length ?? 0, 'file')} rewritten. nothing recomputed, no step added.`,
    )
  } catch (failure) {
    refused(failure)
  } finally {
    branchBusy.value = false
  }
}

// --- changes from behind the newest step ------------------------------------

/**
 * The question every moving op asks first, answered here because this page
 * owns the dialog and the lane the screen lands on. A branch standing on its
 * newest step needs no question. One standing behind — rewound, and left there
 * on purpose — gets asked once per gesture whether the change goes on this
 * lane, moving it on from where it stands, or on a new lane started there.
 */
interface FromHere {
  branch: string
  head: number
  newest: number
  settle: (target: string | null) => void
}

const fromHere = ref<FromHere | null>(null)
const fromHereRefusal = ref<string | null>(null)

/** Open while a gesture waits on the answer; closing it is stepping back. */
const fromHereOpen = computed({
  get: () => fromHere.value !== null,
  set: (open: boolean) => {
    if (!open) settleFromHere(null)
  },
})

function askWhereFrom(branch: string): Promise<string | null> {
  const standing = records.branches.value.find((entry) => entry.name === branch)
  if (!standing || standing.newestStep === undefined || standing.newestStep <= standing.headStep) {
    return Promise.resolve(branch)
  }
  // A second gesture while the first is being asked about gets no answer.
  if (fromHere.value) return Promise.resolve(null)
  fromHereRefusal.value = null
  return new Promise((settle) => {
    fromHere.value = {
      branch,
      head: standing.headStep,
      newest: standing.newestStep as number,
      settle,
    }
  })
}

provide(MOVE_GUARD, askWhereFrom)

function settleFromHere(target: string | null): void {
  const asked = fromHere.value
  fromHere.value = null
  asked?.settle(target)
}

/** A lane from where the branch stands, and the gesture lands on it — so the screen does too. */
async function onLaneFromHere(name: string): Promise<void> {
  const asked = fromHere.value
  if (!asked || branchBusy.value) return
  branchBusy.value = true
  fromHereRefusal.value = null
  try {
    const created = await ops.fork(name, asked.branch)
    selection.viewedBranch.value = created.branch
    acknowledge(
      `Started ${created.branch}`,
      `from ${asked.branch} at step ${asked.head} · ${formatCount(created.cells, 'cell')}.`,
    )
    settleFromHere(created.branch)
  } catch (failure) {
    fromHereRefusal.value = failure instanceof Error ? failure.message : String(failure)
  } finally {
    branchBusy.value = false
  }
}

/** The one op whose content is the user's sentence rather than an auto-intent. */
async function onCheckpoint(intent: string, step: number): Promise<void> {
  if (branchBusy.value) return
  branchBusy.value = true
  try {
    const marked = await ops.checkpoint(intent, viewedBranch.value, step)
    acknowledge(
      `Marked step ${marked.step}`,
      'the words are on the step. nothing was added or copied',
    )
  } catch (failure) {
    refused(failure)
  } finally {
    branchBusy.value = false
  }
}

async function onCheckout(name: string): Promise<void> {
  try {
    await ops.checkout(name)
    // The files now hold this branch, so the screen follows them.
    selection.viewedBranch.value = name
    graphVisible.value = false
  } catch (failure) {
    refused(failure)
  }
}

async function onArchive(name: string): Promise<void> {
  try {
    await ops.archive(name)
  } catch (failure) {
    refused(failure)
  }
}

/**
 * The branches to compare are a selection like any other: they ride the URL, so
 * the comparison is a link and the graph never has to be visited twice.
 */
function onCompare(names: string[]): void {
  selection.compared.value = names
  graphVisible.value = false
  void router.push({
    path: `${route.path.replace(/\/notebook$/, '')}/compare`,
    query: { ...route.query, branch: viewedBranch.value, compare: names.join(',') },
  })
}

function onCheatsheet(): void {
  toast.add({
    severity: 'secondary',
    summary: 'agent guide',
    detail: 'run `lumlflow guide` in a terminal, or read `lumlflow://guide` over MCP.',
    life: 4000,
  })
}

async function onRestartKernel(): Promise<void> {
  try {
    await ops.restartKernel()
    await records.refreshEnv()
  } catch (failure) {
    refused(failure)
  }
}

/**
 * Settings live in the flow's `flow.yaml`, not in the journal — config for what
 * the runtime does next rather than history. The daemon's answer is what the
 * panel then renders, so a refused write leaves the controls where they were.
 */
async function onUpdateSettings(next: FlowSettings): Promise<void> {
  try {
    const written = await ops.saveSettings(settingsReport(next))
    records.applySettings(written.settings)
  } catch (failure) {
    refused(failure)
  }
}
</script>
