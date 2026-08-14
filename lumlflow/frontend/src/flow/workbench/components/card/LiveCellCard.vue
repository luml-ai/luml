<template>
  <div class="min-w-0">
    <CellCard
      :cell="shown"
      :density="density"
      :selected="selected"
      :preflight="preflight ?? closure"
      :awaiters="awaiters"
      :branch="branch"
      :handoff="handoff"
      @handoff="onHandoff"
      @tab="live.showing.value = $event"
      @expand="onExpand"
      @preflight="onPreflight"
      @run="emit('run', $event)"
      @stop="emit('stop')"
      @rename="emit('rename')"
      @delete="onDelete"
      @duplicate="emit('duplicate')"
      @add-downstream="emit('add-downstream')"
      @promote="onPromote"
      @eager="onEager"
      @send-to-agent="emit('send-to-agent', $event)"
      @resolve-conflict="onResolveConflict"
      @edit="onEdit"
      @edit-start="onEditStart"
    />

    <p v-if="notice" class="px-1 pt-1 text-sm text-muted-color">{{ notice }}</p>

    <!-- The kernel-free tier ends at expand, and it is announced before it ends. -->
    <Dialog v-model:visible="asking" modal header="Start the kernel?" :style="{ width: '26rem' }">
      <div class="flex flex-col gap-3">
        <p class="text-base">
          Every card on screen comes from stored previews. Reading
          <code class="font-mono">{{ slug }}</code> out of its stored value is the first gesture
          that needs a kernel.
        </p>
        <KernelStartHint />
        <div class="flex justify-end gap-2 pt-1">
          <Button text severity="secondary" label="stay on previews" @click="asking = false" />
          <Button label="expand and start the kernel" @click="accept" />
        </div>
      </div>
    </Dialog>

    <ExpandDrawer
      v-model:visible="expanded"
      :cell="shown"
      :kernel-started="kernelStarted"
      :page="live.rows.value"
      :paging="live.paging.value"
      :downloading="downloading"
      :notice="notice"
      @tab="live.showing.value = `out:${$event}`"
      @page="onPage"
      @download="onDownload"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, toRef, watch } from 'vue'
import { Button, Dialog } from 'primevue'

import { FlowApiError } from '@/flow/api/client'
import type { FlowStream } from '@/flow/api/stream'
import type { CellSummary, HandoffGesture } from '@/flow/api/types'
import { useCell } from '../../live/useCell'
import type { PageMove } from '../../live/useCell'
import type { FlowSessionHandle } from '../../live/useFlowSession'
import { useFlowOps } from '../../live/useFlowOps'
import { primaryOutput } from '../../model/registry'
import type { FlowCell, Preflight } from '../../model/types'
import KernelStartHint from '../session/KernelStartHint.vue'
import CellCard from './CellCard.vue'
import ExpandDrawer from './ExpandDrawer.vue'

/**
 * One card, bound to the session.
 *
 * The card cluster stays what it was — it renders a `FlowCell` and emits
 * gestures — and this is the seam where that model comes from the daemon
 * instead of a fixture. It owns what is per-card rather than per-page: which
 * tab is on screen, which decides what gets fetched; the expand drawer, because
 * expand is the gesture that may start a kernel; and the ops whose whole
 * context is this cell — its edit, its closure, its own deletion. Gestures that
 * need the page (renaming, forking an edit onto a new branch, handing a payload
 * to an agent) are passed up rather than half-done here.
 */
const props = defineProps<{
  session: FlowSessionHandle
  stream: FlowStream
  branch: string
  summary: CellSummary
  density: 'canvas' | 'notebook'
  selected?: boolean
  preflight?: Preflight
  awaiters?: number
  /** The name this cell answered to before the rename that just landed. */
  renamedFrom?: string
}>()

const emit = defineEmits<{
  run: [payload: { force: boolean }]
  stop: []
  rename: []
  duplicate: []
  'add-downstream': []
  'send-to-agent': [payload: string]
  /** The edit stands and the head moved: forking it needs a branch, not a card. */
  'fork-edit': [payload: { source: string }]
  edit: [payload: { source: string }]
}>()

const live = useCell({
  session: props.session,
  stream: props.stream,
  branch: toRef(props, 'branch'),
  summary: toRef(props, 'summary'),
})

const ops = useFlowOps(props.session)

const slug = computed(() => props.summary.slug)
const kernelStarted = computed(() => props.session.brief.value?.kernel.state === 'running')

const expanded = ref(false)
const asking = ref(false)
const downloading = ref(false)
const notice = ref<string | null>(null)
const closure = ref<Preflight | null>(null)
/** Bumped whenever the closure in hand stops describing the branch it was for. */
let plans = 0
const conflict = ref(false)
const handoff = ref<{ gesture: HandoffGesture; text: string } | null>(null)
const draft = ref<string | null>(null)
const pending = ref(unwritten())
/**
 * The version the open editor started from. Pinned when the editor opens, not
 * read at save: `live.base` follows the head, so an agent's edit landing while
 * the reader types would move it to the very version the lock exists to protect
 * — and the save would sail through as an in-order write.
 */
const editingBase = ref<string | null>(null)

function unwritten(): boolean {
  return props.session.brief.value?.unwritten.includes(slug.value) ?? false
}

/**
 * The card's own two overlays on what the store says: an edit whose transaction
 * has not landed yet, and one that landed but is not in the files. Neither is a
 * verdict the daemon serves — they are what this surface is waiting on.
 */
const shown = computed<FlowCell>(() => ({
  ...live.cell.value,
  conflict: conflict.value || undefined,
  pendingProjection: pending.value || undefined,
  renamedFrom: props.renamedFrom,
}))

function onExpand(): void {
  notice.value = null
  // The drawer replays the run's logs beside the value, so they are wanted
  // whether or not the reader ever opened the card's logs tab.
  live.readLogs()
  if (!kernelStarted.value) {
    asking.value = true
    return
  }
  expanded.value = true
}

function accept(): void {
  asking.value = false
  expanded.value = true
}

/** Paging is the request that actually starts the kernel, not opening the drawer. */
async function onPage(request: { output: string; move: PageMove }): Promise<void> {
  await live.readPage(request.output, request.move)
  if (live.refusal.value) notice.value = live.refusal.value
}

/**
 * Download, and the run that has to happen first when this branch holds no
 * value yet. Both outcomes are stated: a path, or the sentence the daemon
 * refused with.
 */
async function onDownload(request: { output: string; materialize: boolean }): Promise<void> {
  downloading.value = true
  notice.value = request.materialize ? `materializing ${slug.value}…` : null
  try {
    if (request.materialize) await ops.run(slug.value, { branch: props.branch })
    const saved = await live.download(request.output)
    notice.value = `saved to ${saved.path}`
  } catch (refused) {
    notice.value = said(refused)
  } finally {
    downloading.value = false
  }
}

/**
 * The closure, asked for when the popover opens rather than for every card on
 * screen. Twenty cards preflighting themselves on render is twenty plans the
 * daemon computed for a question nobody asked.
 */
async function onPreflight(): Promise<void> {
  const asked = plans
  try {
    const answer = await ops.preflight(slug.value, props.branch)
    // A plan the branch moved out from under is worse than no plan: the popover
    // says it is still asking, and a confident number for a head that has since
    // changed is what "run never happens blind" exists to prevent.
    if (asked !== plans) return
    closure.value = {
      cached: answer.cached,
      recompute: answer.recompute,
      unknown: answer.unknown,
      totalSeconds: answer.estimate_seconds,
    }
  } catch (refused) {
    notice.value = said(refused)
  }
}

/**
 * An edit carries the version it started from. The daemon compares it against
 * the head and refuses when they differ, which is the only way a UI edit and an
 * agent's edit of the same cell can both be kept: nothing is written until the
 * reader picks a side.
 */
function onEditStart(): void {
  editingBase.value = live.base.value
}

async function onEdit(payload: { source: string }): Promise<void> {
  await land(payload.source, {})
}

async function onResolveConflict(choice: 'overwrite' | 'fork'): Promise<void> {
  const source = draft.value
  if (source === null) return
  if (choice === 'fork') {
    // Forking needs a branch to fork, which is the page's business; the draft
    // travels with the gesture so nothing has to be retyped. It also *stays*
    // here until the fork lands — a fork the daemon refuses would otherwise
    // take the only copy of what the reader typed with it, and the menu it was
    // typed under is the one place left offering to overwrite instead.
    emit('fork-edit', { source })
    return
  }
  await land(source, { force: true })
}

async function land(source: string, options: { force?: boolean }): Promise<void> {
  draft.value = source
  // Optimistic only where the store is: the edit reads as pending until the
  // daemon has taken it, because until then it may still come back a conflict.
  notice.value = 'saving…'
  try {
    const written = await ops.edit(slug.value, source, {
      branch: props.branch,
      base: editingBase.value ?? live.base.value ?? undefined,
      force: options.force,
    })
    conflict.value = false
    draft.value = null
    editingBase.value = null
    // Saved either way; whether the files have it yet is the worktree lock's
    // answer, and the card says which of the two happened.
    pending.value = !written.written_to_files
    notice.value = null
  } catch (refused) {
    if (refused instanceof FlowApiError && refused.kind === 'EditConflict') {
      conflict.value = true
      notice.value = refused.message
      return
    }
    notice.value = said(refused)
  }
}

async function onDelete(): Promise<void> {
  try {
    const gone = await ops.deleteCell(slug.value, { branch: props.branch })
    notice.value = gone.dangling.length
      ? `${gone.dangling.join(', ')} now point at nothing on ${props.branch}`
      : null
  } catch (refused) {
    notice.value = said(refused)
  }
}

async function onEager(on: boolean): Promise<void> {
  try {
    await ops.setEager(slug.value, on, props.branch)
    notice.value = on
      ? 'eager. rematerializes on change whatever it costs.'
      : 'back to the flow’s reactivity setting'
  } catch (refused) {
    notice.value = said(refused)
  }
}

/**
 * The payload behind a handoff popover, asked for when it opens.
 *
 * The daemon builds it because the daemon has it: *fix this* carries the
 * traceback of the run this branch observed whether or not anyone opened the
 * logs tab. Asked for on open rather than per card — twenty cards each holding
 * two payloads nobody read is twenty round trips for a gesture not made.
 */
async function onHandoff(gesture: HandoffGesture): Promise<void> {
  try {
    const built = await ops.handoff(gesture, { branch: props.branch, slug: slug.value })
    handoff.value = { gesture, text: built.text }
  } catch (refused) {
    notice.value = said(refused)
  }
}

async function onPromote(): Promise<void> {
  const primary = primaryOutput(live.cell.value)
  if (!primary) return
  try {
    const published = await ops.promote(`${slug.value}.${primary.name}`, props.branch)
    notice.value = `${primary.name} · upload ${published.state}`
  } catch (refused) {
    notice.value = said(refused)
  }
}

function said(refused: unknown): string {
  return refused instanceof Error ? refused.message : String(refused)
}

// A drawer left open across a rewind or a rerun is showing the old window;
// the fresh one is a page request away, and the preview stands until then. The
// closure goes with it: a plan made before the last transaction is a plan for a
// branch that has moved. `plans` is what an answer still in flight is checked
// against, so the discarded plan cannot land after its own reset.
watch([() => props.branch, () => props.session.head.value], () => {
  notice.value = null
  closure.value = null
  // A payload quotes a traceback and a state; both are as of the step it was
  // built at, and handing an agent the previous run's error is worse than
  // asking for it again.
  handoff.value = null
  plans += 1
})

/**
 * A draft belongs to the branch it was typed against. Viewing another branch is
 * free and reuses this card, so carrying the conflict menu across would offer to
 * overwrite a version the edit was never based on — on a branch nobody edited.
 */
watch(
  () => props.branch,
  () => {
    conflict.value = false
    draft.value = null
    editingBase.value = null
    pending.value = unwritten()
  },
)

// The lock is what held the write back, so the holder leaving is what completes
// it — the same moment the daemon drains its deferred projections.
watch(
  () => props.session.agent.value,
  (paired) => {
    if (!paired) pending.value = false
  },
)
</script>
