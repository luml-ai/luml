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
        </div>

        <div class="min-h-0 flex-1">
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
import { Plus } from 'lucide-vue-next'

import { FlowApiError } from '@/flow/api/client'
import type { FlowStream } from '@/flow/api/stream'
import type { CellSummary } from '@/flow/api/types'
import FromHereDialog from '../components/branch/FromHereDialog.vue'
import NewBranchDialog from '../components/branch/NewBranchDialog.vue'
import FlowCanvas, { type CanvasSessionState } from '../components/canvas/FlowCanvas.vue'
import AgentEndedBanner from '../components/card/AgentEndedBanner.vue'
import KernelDeathBanner from '../components/card/KernelDeathBanner.vue'
import LiveCellCard from '../components/card/LiveCellCard.vue'
import BranchGraphOverlay from '../components/graph/BranchGraphOverlay.vue'
import LeftPanel from '../components/panel/LeftPanel.vue'
import SessionBanners from '../components/session/SessionBanners.vue'
import { coalesceTransactions } from '../live/toasts'
import { formatCount } from '../model/format'
import { reorderNeighbours } from '../model/registry'
import { summarized } from '../live/useCell'
import { MOVE_GUARD, MoveCancelled, useFlowOps } from '../live/useFlowOps'
import { useAgentHarnesses } from '../live/useAgentHarnesses'
import type { FlowSessionHandle } from '../live/useFlowSession'
import { useSelection } from '../live/useSelection'
import { useSlice } from '../live/useSlice'
import { settingsReport, useWorkbench } from '../live/useWorkbench'
import type { FlowSettings, Preflight, StaleCounts } from '../model/types'
import EmptyFlowState from './EmptyFlowState.vue'
import NotebookColumn from './NotebookColumn.vue'
import WorkbenchTopBar from './WorkbenchTopBar.vue'

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

const showTint = ref(false)

const unsynced = computed(() => slice.direct.value.filter((cell) => cell.state === 'unsynced'))
const unmaterialized = computed(() =>
  slice.direct.value.filter((cell) => cell.state === 'unmaterialized'),
)
const transitive = computed(() => slice.transitive.value)

const shown = computed<CellSummary[]>(() =>
  slice.cells.value.map((cell) =>
    cell.transitive && !showTint.value ? { ...cell, transitive: false, upstream: [] } : cell,
  ),
)

const shownBySlug = computed(() => new Map(shown.value.map((cell) => [cell.slug, cell])))

const running = computed(() => new Set(session.running.value.map((entry) => entry.slug)))

const cells = computed(() =>
  shown.value.map((summary) => summarized(summary, running.value.has(summary.slug))),
)

const moveNeighbours = computed(() => reorderNeighbours(cells.value))

const tintedSlugs = computed(
  () => new Set(showTint.value ? transitive.value.map((cell) => cell.slug) : []),
)

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

function onSelect(slug: string): void {
  if (selection.selectedSlug.value === slug) return
  selection.selectedSlug.value = slug
}

watch(shownBySlug, (bySlug) => {
  const slug = selection.selectedSlug.value
  if (slug && bySlug.size > 0 && !bySlug.has(slug)) selection.selectedSlug.value = null
})

function cardProps(slug: string, selected: boolean, density: 'canvas' | 'notebook') {
  const moves = moveNeighbours.value.get(slug)
  return {
    session,
    stream: props.stream,
    branch: viewedBranch.value,
    summary: shownBySlug.value.get(slug)!,
    density,
    selected,
    awaiters: Math.max(0, (inFlight.value.get(slug)?.awaiting ?? 1) - 1),
    renamedFrom: justRenamed.value.get(slug),
    canMoveUp: moves !== undefined && moves.up !== null,
    canMoveDown: moves !== undefined && moves.down !== null,
  }
}

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

const openedBehind = ref(session.changesBehind.value)

watch(session.changesBehind, (count) => {
  if (count > openedBehind.value) openedBehind.value = count
})

const graphVisible = ref(false)

const panelOpen = ref<string[]>(['cells'])
const renaming = ref(false)
const renameFrom = ref('')
const renameTo = ref('')
const branchClosure = ref<Preflight | null>(null)
let plans = 0
const kernelDeath = ref<{ slug: string; cause?: string } | null>(null)

function refused(failure: unknown): void {
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

async function onDuplicate(slug: string): Promise<void> {
  try {
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

const harnesses = useAgentHarnesses(
  {
    list: () => session.request('agents.harnesses', {}),
    setup: (id, consent) => session.request('agents.setup', { harness: id, consent }),
    remove: (id) => session.request('agents.remove', { harness: id }),
  },
  refused,
)
const agents = harnesses.harnesses
const agentsLoading = harnesses.loading
const agentsError = harnesses.loadError
const agentBusyIds = harnesses.busyIds

function onPair(): void {
  if (!panelOpen.value.includes('agents')) {
    panelOpen.value = [...panelOpen.value, 'agents']
    return
  }
  void onOpenAgents()
}

function onOpenAgents(): Promise<void> {
  return harnesses.refresh()
}

function onSetupAgents(ids: string[], consent: boolean): Promise<void> {
  return harnesses.setup(ids, consent)
}

function onUpdateAgent(id: string): void {
  harnesses.update(id)
}

function onRemoveAgent(id: string): Promise<void> {
  return harnesses.remove(id)
}

function onOpenActivity(): void {
  if (!panelOpen.value.includes('activity')) panelOpen.value = [...panelOpen.value, 'activity']
  session.markSeen()
}

async function onRestartAfterDeath(): Promise<void> {
  kernelDeath.value = null
  await onRestartKernel()
}

watch([viewedBranch, () => session.head.value], () => {
  branchClosure.value = null
  plans += 1
})

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

const endedUnder = computed(() => {
  if (!agentEnded.value) return null
  if (failedCell.value) return failedCell.value.slug
  return endedUnsynced.value.at(-1)?.slug ?? null
})

function onViewBranch(name: string): void {
  selection.viewedBranch.value = name
  graphVisible.value = false
}

const forking = ref(false)
const forkRefusal = ref<string | null>(null)

const branchBusy = ref(false)

function onNewBranch(): void {
  forkRefusal.value = null
  forking.value = true
}

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
    forkRefusal.value = failure instanceof Error ? failure.message : String(failure)
  } finally {
    branchBusy.value = false
  }
}

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

interface FromHere {
  branch: string
  head: number
  newest: number
  settle: (target: string | null) => void
}

const fromHere = ref<FromHere | null>(null)
const fromHereRefusal = ref<string | null>(null)

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

async function onUpdateSettings(next: FlowSettings): Promise<void> {
  try {
    const written = await ops.saveSettings(settingsReport(next))
    records.applySettings(written.settings)
  } catch (failure) {
    refused(failure)
  }
}
</script>
