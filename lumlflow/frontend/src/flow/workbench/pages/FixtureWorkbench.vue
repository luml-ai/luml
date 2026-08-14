<template>
  <div class="flex h-full min-h-0 flex-col gap-3">
    <DaemonDownBanner v-if="opsDisabled" />

    <WorkbenchTopBar
      v-model:view="view"
      v-model:show-tint="showTint"
      :session="wb.session"
      :viewed-branch="viewedBranch"
      :branches="branches"
      :branch-preflight="branchPreflight"
      :runnable="hasCells"
      :ops-disabled="opsDisabled"
      :stale="staleCounts"
      @rerun-branch="onRerunBranch"
      @stop-session="onStopSession"
      @open-catchup="onOpenCatchup"
      @view-branch="onGraphView"
      @checkout-branch="onGraphCheckout"
      @new-branch="onNewBranch"
    />

    <WorktreeLockNotice
      v-if="wb.variant === 'locked'"
      :holder="wb.session.paired?.label"
      @force="onForceWorktree"
    />

    <div class="flex min-h-0 flex-1 gap-3">
      <aside
        class="w-80 shrink-0 min-h-0 overflow-hidden rounded-lg border border-surface-200 dark:border-surface-700"
      >
        <LeftPanel
          v-model:open="panelOpen"
          :branches="branches"
          :cells="slice"
          :viewed-branch="viewedBranch"
          :session="wb.session"
          :env="wb.env"
          :settings="settings"
          :journal="journal"
          :behind="wb.session.changesBehind"
          @open-graph="graphVisible = true"
          @new-branch="onNewBranch"
          @rewind="onRewind"
          @checkpoint="onCheckpoint"
          @select-cell="onSelectCell"
          @summarize-branch="onSummarizeBranch"
          @update-settings="onUpdateSettings"
        />
      </aside>

      <main class="flex min-h-0 min-w-0 flex-1 flex-col gap-3">
        <!--
          Pairing is said once, in the left panel: a workbench with cells on it
          is working software, and an agent it does not have is not a blocker
          that earns a banner above the work.
        -->
        <div v-if="kernelHint" class="px-1">
          <KernelStartHint />
        </div>

        <div class="min-h-0 flex-1" :class="opsDisabled ? 'opacity-60' : ''">
          <EmptyFlowState
            v-if="!hasCells"
            :paired="wb.session.paired"
            @cheatsheet="onCheatsheet"
            @notebook="view = 'notebook'"
            @create="onCreateCell"
          />
          <FlowCanvas
            v-else-if="view === 'canvas'"
            class="h-full rounded-lg border border-surface-200 dark:border-surface-700"
            :cells="displayCells"
            :branch="viewedBranch"
            :selected-slug="selectedSlug"
            :tinted-slugs="tintedSlugs"
            :preflights="preflights"
            @select="onSelect"
            @expand="onExpand"
            @run="onRun"
            @stop="onStopCell"
            @rename="onRename"
            @delete="onDelete"
            @duplicate="onDuplicate"
            @send-to-agent="onSendToAgent"
            @resolve-conflict="onResolveConflict"
            @edit="onEdit"
          />
          <NotebookColumn
            v-else
            :cells="displayCells"
            :branch="viewedBranch"
            :selected-slug="selectedSlug"
            :tinted-slugs="tintedSlugs"
            :preflights="preflights"
            @select="onSelect"
            @expand="onExpand"
            @run="onRun"
            @stop="onStopCell"
            @rename="onRename"
            @delete="onDelete"
            @duplicate="onDuplicate"
            @send-to-agent="onSendToAgent"
            @resolve-conflict="onResolveConflict"
            @edit="onEdit"
          />
        </div>
      </main>
    </div>

    <NewBranchDialog v-model:visible="forking" :from="viewedBranch" @create="onFork" />

    <BranchGraphOverlay
      v-model:visible="graphVisible"
      :branches="branches"
      :worktree-locked="wb.session.worktreeLocked"
      @view="onGraphView"
      @checkout="onGraphCheckout"
      @archive="onGraphArchive"
      @compare="onGraphCompare"
    />

    <ExpandDrawer
      v-if="expandCell"
      v-model:visible="drawerVisible"
      :cell="expandCell"
      :kernel-started="kernelStarted"
    />

    <!-- The kernel-free tier ends here: expand is the first gesture that starts one. -->
    <Dialog
      v-model:visible="hintVisible"
      modal
      header="Start the kernel?"
      :style="{ width: '26rem' }"
    >
      <div class="flex flex-col gap-3">
        <p class="text-base">
          Browsing works from stored previews. Expanding
          <code class="font-mono">{{ expandSlug }}</code> into its full value is the first gesture
          that needs a kernel.
        </p>
        <KernelStartHint />
        <div class="flex justify-end gap-2 pt-1">
          <Button text severity="secondary" label="stay on previews" @click="hintVisible = false" />
          <Button label="expand and start the kernel" @click="confirmKernelStart" />
        </div>
      </div>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button, Dialog } from 'primevue'
import { useToast } from 'primevue/usetoast'
import NewBranchDialog from '../components/branch/NewBranchDialog.vue'
import FlowCanvas from '../components/canvas/FlowCanvas.vue'
import ExpandDrawer from '../components/card/ExpandDrawer.vue'
import BranchGraphOverlay from '../components/graph/BranchGraphOverlay.vue'
import LeftPanel from '../components/panel/LeftPanel.vue'
import DaemonDownBanner from '../components/session/DaemonDownBanner.vue'
import KernelStartHint from '../components/session/KernelStartHint.vue'
import WorktreeLockNotice from '../components/session/WorktreeLockNotice.vue'
import { evalPreflight } from '../fixtures'
import { formatCost, formatCount } from '../model/format'
import type {
  BranchInfo,
  FlowCell,
  FlowSettings,
  JournalEntry,
  Preflight,
  StaleCounts,
} from '../model/types'
import EmptyFlowState from './EmptyFlowState.vue'
import NotebookColumn from './NotebookColumn.vue'
import WorkbenchTopBar from './WorkbenchTopBar.vue'
import { useWorkbenchState } from './useWorkbenchState'

/**
 * The workbench over the fixture: one screen, two views. Left is the viewed
 * branch and its inventory; center is canvas or notebook over the SAME branch
 * slice. View, selection, and viewed branch live in the URL so links are
 * shareable and the two views can never disagree.
 *
 * This is the arm the design gallery and the specs mount — every `?state=`
 * variant is a moment of the same flow, authored rather than fetched. The live
 * arm beside it is `LiveWorkbench.vue`, and the two render the same components.
 */
const route = useRoute()
const router = useRouter()
const toast = useToast()

const wb = useWorkbenchState(route)

const opsDisabled = wb.variant === 'not-running'

// --- URL-synced selection ---------------------------------------------------

// The view is the route's last segment (`/flow/<flow>/notebook`); `?view=` is
// still honoured so older links land where they meant to.
const NOTEBOOK_SEGMENT = '/notebook'
const flowPath = route.path.endsWith(NOTEBOOK_SEGMENT)
  ? route.path.slice(0, -NOTEBOOK_SEGMENT.length)
  : route.path

const view = ref<'canvas' | 'notebook'>(
  route.path.endsWith(NOTEBOOK_SEGMENT) || route.query.view === 'notebook' ? 'notebook' : 'canvas',
)
const selectedSlug = ref<string | null>(
  typeof route.query.asset === 'string' && route.query.asset ? route.query.asset : null,
)
const branchNames = new Set(wb.branches.map((branch) => branch.name))
const viewedBranch = ref(
  typeof route.query.branch === 'string' && branchNames.has(route.query.branch)
    ? route.query.branch
    : wb.session.worktreeBranch,
)

// FlowShell keys its RouterView on route.fullPath, so a router.replace would
// remount the whole page on every selection change (canvas refit, drawer
// close). The URL is mirrored with history.replaceState instead: same
// shareable links, no remount.
watch([view, selectedSlug, viewedBranch], () => {
  const params = new URLSearchParams()
  if (typeof route.query.state === 'string') params.set('state', route.query.state)
  if (selectedSlug.value) params.set('asset', selectedSlug.value)
  if (viewedBranch.value !== wb.session.worktreeBranch) params.set('branch', viewedBranch.value)
  const search = params.toString()
  const path = `${flowPath}${view.value === 'notebook' ? NOTEBOOK_SEGMENT : ''}`
  window.history.replaceState(window.history.state, '', `${path}${search ? `?${search}` : ''}`)
})

// --- branches, and the two ops that add to them ------------------------------

/**
 * The fixture's own copies, so the branch ops on this arm land somewhere the
 * screen can show. The fixtures module is never mutated — a gallery route that
 * edited it would leak the change into every other route in the tab.
 *
 * Only the two ops that *add* are carried out here: forking a branch and
 * marking a point are both one new row, which a fixture can honestly produce.
 * Rewinding restores a selection history this arm does not have, so it says
 * what it would do rather than inventing a state to move to.
 */
const branches = ref<BranchInfo[]>(wb.branches.map((branch) => ({ ...branch })))
const journal = ref<JournalEntry[]>(wb.journal.map((entry) => ({ ...entry })))
const cellsByBranch = ref<Record<string, FlowCell[]>>({ ...wb.cellsByBranch })

// --- the viewed slice and its staleness -------------------------------------

const slice = computed<FlowCell[]>(() => cellsByBranch.value[viewedBranch.value] ?? [])
const hasCells = computed(() => slice.value.length > 0)

const directStale = computed(() =>
  slice.value.filter((cell) => cell.stale && !cell.stale.transitive),
)
const transitiveStale = computed(() => slice.value.filter((cell) => cell.stale?.transitive))
const hasStale = computed(() => directStale.value.length > 0 || transitiveStale.value.length > 0)

const showTint = ref(false)

/** What the bar states: the counts, and the first stale cell's own words. */
const staleCounts = computed<StaleCounts | undefined>(() => {
  if (!hasStale.value) return undefined
  return {
    unsynced: directStale.value.length,
    downstream: transitiveStale.value.length,
    unmaterialized: slice.value.filter((cell) => cell.status === 'unmaterialized').length,
    cause: directStale.value[0]?.stale?.cause,
  }
})

// Default OFF: transitive cells drop their stale chip; the header count keeps
// the staleness visible, so nothing is SILENTLY fresh-looking.
const displayCells = computed<FlowCell[]>(() => {
  if (showTint.value) return slice.value
  return slice.value.map((cell): FlowCell => {
    if (!cell.stale?.transitive) return cell
    return {
      ...cell,
      status: cell.status === 'stale' ? 'materialized' : cell.status,
      stale: undefined,
    }
  })
})

const tintedSlugs = computed<Set<string>>(() =>
  showTint.value ? new Set(transitiveStale.value.map((cell) => cell.slug)) : new Set(),
)

// --- preflights -------------------------------------------------------------

function cheapPreflightFor(cell: FlowCell): Preflight {
  const seconds = cell.timing?.costSeconds
  return {
    cached: [],
    recompute: [cell.slug],
    unknown: seconds === undefined ? [cell.slug] : [],
    totalSeconds: seconds ?? 0,
  }
}

const preflights = computed<Record<string, Preflight | undefined>>(() =>
  Object.fromEntries(
    slice.value.map((cell) => [
      cell.slug,
      cell.slug === 'train_model' ? evalPreflight : cheapPreflightFor(cell),
    ]),
  ),
)

/** Rerun-to-leaves batch, built from the stale cells' recorded timings. */
const branchPreflight = computed<Preflight | null>(() => {
  const cells = slice.value.filter((cell) => !cell.isNote)
  if (cells.length === 0) return null
  const needsRun = (cell: FlowCell): boolean =>
    Boolean(cell.stale) ||
    cell.status === 'stale' ||
    cell.status === 'unmaterialized' ||
    cell.status === 'failed'
  const recompute = cells.filter(needsRun)
  return {
    cached: cells.filter((cell) => !needsRun(cell)).map((cell) => cell.slug),
    recompute: recompute.map((cell) => cell.slug),
    unknown: recompute.filter((cell) => !cell.timing?.costSeconds).map((cell) => cell.slug),
    totalSeconds: recompute.reduce((sum, cell) => sum + (cell.timing?.costSeconds ?? 0), 0),
  }
})

// --- toasts: every op acknowledges, and a stopped server says why it cannot --

function ack(
  summary: string,
  detail: string,
  severity: 'secondary' | 'info' | 'warn' = 'secondary',
): void {
  if (opsDisabled) {
    toast.add({
      severity: 'warn',
      summary: 'lumlflow is not running',
      detail: 'nothing live to receive this op. showing last-known state.',
      life: 3000,
    })
    return
  }
  toast.add({ severity, summary, detail, life: 3200 })
}

// --- selection and cross-navigation -----------------------------------------

function onSelect(slug: string): void {
  selectedSlug.value = slug
}

function onSelectCell(slug: string): void {
  selectedSlug.value = slug
}

// --- expand and the kernel boundary -----------------------------------------

const expandSlug = ref<string | null>(null)
const drawerVisible = ref(false)
const hintVisible = ref(false)
const kernelStarted = ref(wb.variant !== 'kernel-not-started')

const expandCell = computed(
  () => slice.value.find((cell) => cell.slug === expandSlug.value) ?? null,
)

const kernelHint = computed(() => wb.variant === 'kernel-not-started' && !kernelStarted.value)

function onExpand(slug: string): void {
  expandSlug.value = slug
  if (!kernelStarted.value) {
    hintVisible.value = true
    return
  }
  drawerVisible.value = true
}

function confirmKernelStart(): void {
  hintVisible.value = false
  kernelStarted.value = true
  drawerVisible.value = true
  toast.add({
    severity: 'info',
    summary: 'Kernel starting',
    detail: 'previews never needed one. expand is the first gesture that does.',
    life: 2500,
  })
}

// --- card ops ----------------------------------------------------------------

function onRun(slug: string, payload: { force: boolean }): void {
  const preflight = preflights.value[slug]
  const scope = preflight
    ? `${formatCount(preflight.recompute.length, 'cell')} · ~${formatCost(preflight.totalSeconds)}`
    : slug
  ack(
    `Run ${slug}`,
    payload.force ? `force rerun · memo ignored · ${scope}` : `minimal stale closure · ${scope}`,
    'info',
  )
}

function onStopCell(slug: string): void {
  ack(`Stop ${slug}`, 'cancels when no other awaiter still wants the result', 'info')
}

function onRename(slug: string): void {
  ack(
    `Rename ${slug}`,
    'free. every reference rewires atomically. it touches no cache and no history.',
  )
}

function onDelete(slug: string): void {
  ack(
    `Deleted ${slug} from ${viewedBranch.value}`,
    'this lane’s selection only. other lanes keep it. consumers here show a flagged reference.',
  )
}

function onDuplicate(slug: string): void {
  ack(
    `Duplicated ${slug}`,
    'a fresh identity with no consumers. a new lane is usually the better move.',
  )
}

function onSendToAgent(slug: string, payload: string): void {
  const label = wb.session.paired?.label
  if (label) {
    ack(
      `Handed to ${label}`,
      `context payload for ${slug} · ${formatCount(payload.split('\n').length, 'line')}`,
      'info',
    )
  } else {
    ack(
      'No agent paired',
      'copy the payload from the popover and paste it into your agent’s terminal',
      'warn',
    )
  }
}

function onResolveConflict(slug: string, choice: 'overwrite' | 'fork'): void {
  ack(
    choice === 'fork' ? `Saved your edit of ${slug} to a new lane` : `Overwrote ${slug}`,
    choice === 'fork'
      ? 'your version lands on a new lane. the agent’s newer version stays where it is.'
      : 'your version replaces the newer one. the agent’s edit stays in history.',
    'info',
  )
}

function onEdit(slug: string): void {
  ack(
    `Edit of ${slug} saved to the store`,
    wb.session.worktreeLocked
      ? 'the agent holds the files. the write to them waits.'
      : 'written to the flow files',
    'info',
  )
}

// --- session ops -------------------------------------------------------------

function onRerunBranch(payload: { force: boolean }): void {
  const preflight = branchPreflight.value
  if (!preflight) return
  ack(
    `Rerun ${viewedBranch.value}`,
    `runs the slice to its leaves · ${formatCount(preflight.recompute.length, 'recompute')}${
      payload.force ? ' plus every memo hit (force)' : ''
    } · ~${formatCost(preflight.totalSeconds)}${payload.force ? '+' : ''}`,
    'info',
  )
}

function onStopSession(): void {
  ack(
    'Session stopped',
    'cancels the run and drains the queue. the agent in your terminal is untouched.',
    'info',
  )
}

/** The marker's destination is the panel's activity section, its one home. */
function onOpenCatchup(): void {
  if (!panelOpen.value.includes('activity')) panelOpen.value = [...panelOpen.value, 'activity']
}

function onForceWorktree(): void {
  ack(
    'Files taken',
    'the agent loses its file view until it re-registers. its edits stay in the store.',
    'warn',
  )
}

function onSummarizeBranch(): void {
  const label = wb.session.paired?.label
  ack(
    'Summarize this lane',
    label
      ? `lane payload handed to ${label}. it writes the note cell.`
      : 'no agent paired. pair one and the payload is ready to hand over.',
    label ? 'info' : 'warn',
  )
}

// --- settings ----------------------------------------------------------------

const settings = ref<FlowSettings>({ ...wb.settings })

function onUpdateSettings(next: FlowSettings): void {
  settings.value = next
  ack('Settings updated', 'reactivity and env-change policy are per-flow, stored with the flow')
}

// --- branch graph ------------------------------------------------------------

const graphVisible = ref(false)

/** Which panel sections are open — the catch-up marker's destination. */
const panelOpen = ref<string[]>(['cells'])

function onGraphView(name: string): void {
  viewedBranch.value = name
  if (!(cellsByBranch.value[name] ?? []).some((cell) => cell.slug === selectedSlug.value)) {
    selectedSlug.value = null
  }
  graphVisible.value = false
}

// --- branch ops ---------------------------------------------------------------

const forking = ref(false)

function onNewBranch(): void {
  forking.value = true
}

/**
 * A fork is a selection copy: the new branch starts holding exactly what its
 * parent held, which is why it is instant and why nothing is duplicated.
 */
function onFork(name: string): void {
  const from = viewedBranch.value
  if (branches.value.some((branch) => branch.name === name)) {
    ack(`${name} already exists`, 'lane names are unique within a flow', 'warn')
    return
  }
  const parent = branches.value.find((branch) => branch.name === from)
  const step = (parent?.headStep ?? 0) + 1
  branches.value = [
    ...branches.value,
    {
      name,
      parent: from,
      forkedAtStep: step,
      headStep: step,
      lastIntent: `started ${name} from ${from}`,
      settled: parent?.settled ?? false,
    },
  ]
  cellsByBranch.value = { ...cellsByBranch.value, [name]: cellsByBranch.value[from] ?? [] }
  journal.value = [entryAt(step, `started ${name} from ${from}`, 'fork', name), ...journal.value]
  forking.value = false
  viewedBranch.value = name
  ack(`Started ${name}`, `from ${from}. no file and no value is copied.`)
}

function onCheckpoint(intent: string): void {
  const branch = viewedBranch.value
  const step = head(branch) + 1
  journal.value = [entryAt(step, intent, 'checkpoint', branch), ...journal.value]
  branches.value = branches.value.map((entry) =>
    entry.name === branch ? { ...entry, headStep: step, checkpointStep: step } : entry,
  )
  ack(`Marked step ${step}`, 'a place in the history, not a copy of anything')
}

function onRewind(step: number): void {
  ack(
    `Would rewind ${viewedBranch.value} to step ${step}`,
    'restores the selection it held then. nothing recomputes. nothing is lost.',
    'info',
  )
}

function head(branch: string): number {
  return branches.value.find((entry) => entry.name === branch)?.headStep ?? 0
}

function entryAt(
  step: number,
  intent: string,
  kind: JournalEntry['kind'],
  branch: string,
): JournalEntry {
  const now = new Date()
  return {
    step,
    time: `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`,
    branch,
    actor: { kind: 'user', label: 'user' },
    intent,
    kind,
    summary: '',
  }
}

function onGraphCheckout(name: string): void {
  if (wb.session.worktreeLocked) {
    ack(
      `using ${name} here waits`,
      'the agent holds the files. binding them to another lane waits, or forces.',
      'warn',
    )
    return
  }
  ack(`Would use ${name} here`, 'binds the flow files to this lane', 'info')
}

function onGraphArchive(name: string): void {
  ack(`Archived ${name}`, 'collapsed behind the archived toggle. nothing is deleted.')
}

function onGraphCompare(): void {
  graphVisible.value = false
  void router.push(`${flowPath}/compare`)
}

// --- fixture-only doors ------------------------------------------------------

/**
 * The live arm scaffolds a cell through the daemon; the fixture arm has no
 * store to write to, so it acknowledges. Both arms wire the handler — an
 * unwired one is a dead button on every gallery route.
 */
function onCreateCell(): void {
  ack('Add a cell', 'adds an empty cell to this lane. name it and write its materialize.')
}

function onCheatsheet(): void {
  toast.add({
    severity: 'secondary',
    summary: 'Fixture only',
    detail: 'AGENTS.md opens from the flow directory. no surface behind it in this draft.',
    life: 2500,
  })
}
</script>
