<template>
  <div class="min-w-0">
    <CellCard
      v-model:editing="editing"
      v-model:draft="editorDraft"
      :cell="shown"
      :density="density"
      :selected="selected"
      :preflight="preflight ?? closure"
      :awaiters="awaiters"
      :can-move-up="canMoveUp"
      :can-move-down="canMoveDown"
      :detail-loaded="live.detailLoaded.value"
      :publish-model="live.publish"
      @copy-context="onCopyContext"
      @tab="live.showing.value = $event"
      @expand="onExpand"
      @preflight="onPreflight"
      @run="emit('run', $event)"
      @stop="emit('stop')"
      @rename="emit('rename')"
      @delete="onDelete"
      @duplicate="emit('duplicate')"
      @add-downstream="emit('add-downstream')"
      @move-up="emit('move-up')"
      @move-down="emit('move-down')"
      @eager="onEager"
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
      :publish-model="live.publish"
      @tab="live.showing.value = `out:${$event}`"
      @page="onPage"
      @download="onDownload"
    />

    <NewBranchDialog
      v-model:visible="forking"
      :from="branch"
      :initial-name="`${slug}-edit`"
      :refusal="forkRefusal"
      :busy="forkBusy"
      @create="onForkEdit"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, toRef, watch } from 'vue'
import { Button, Dialog } from 'primevue'

import { FlowApiError } from '@/flow/api/client'
import type { FlowStream } from '@/flow/api/stream'
import type { CellSummary } from '@/flow/api/types'
import { useCell } from '../../live/useCell'
import type { PageMove } from '../../live/useCell'
import type { FlowSessionHandle } from '../../live/useFlowSession'
import { MoveCancelled, useFlowOps } from '../../live/useFlowOps'
import type { FlowCell, Preflight } from '../../model/types'
import NewBranchDialog from '../branch/NewBranchDialog.vue'
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
 * context is this cell — its edit, its closure, deletion, and copied context.
 * Renaming still passes up for page state; a forked edit owns its naming dialog
 * here and reports only the lane the page should view.
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
  canMoveUp?: boolean
  canMoveDown?: boolean
  /** The name this cell answered to before the rename that just landed. */
  renamedFrom?: string
}>()

const emit = defineEmits<{
  run: [payload: { force: boolean }]
  stop: []
  rename: []
  duplicate: []
  'add-downstream': []
  'move-up': []
  'move-down': []
  'view-branch': [name: string]
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
const draft = ref<string | null>(null)
const editing = ref(false)
const editorDraft = ref('')
const forking = ref(false)
const forkBusy = ref(false)
const forkRefusal = ref<string | null>(null)
const carryingDraftTo = ref<string | null>(null)
/**
 * The version the open editor started from. Pinned when the editor opens, not
 * read at save: `live.base` follows the head, so an agent's edit landing while
 * the reader types would move it to the very version the optimistic check
 * exists to protect — and the save would sail through as an in-order write.
 */
const editingBase = ref<string | null>(null)

const shown = computed<FlowCell>(() => ({
  ...live.cell.value,
  conflict: conflict.value || undefined,
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
 * value yet. Stored bytes cross the browser route; nothing is copied into the
 * daemon's working directory.
 */
async function onDownload(request: { output: string; materialize: boolean }): Promise<void> {
  downloading.value = true
  notice.value = request.materialize ? `materializing ${slug.value}…` : null
  try {
    if (request.materialize) {
      const outcome = await ops.run(slug.value, { branch: props.branch })
      if (outcome.failed) {
        notice.value = null
        return
      }
    }
    startDownload(live.downloadUrl(request.output))
    notice.value = null
  } catch (refused) {
    notice.value = said(refused)
  } finally {
    downloading.value = false
  }
}

function startDownload(url: string): void {
  const link = document.createElement('a')
  link.href = url
  link.download = ''
  document.body.append(link)
  link.click()
  link.remove()
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
      reasons: answer.reasons ?? [],
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
    forkRefusal.value = null
    forking.value = true
    return
  }
  await land(source, { force: true })
}

async function onForkEdit(name: string): Promise<void> {
  if (forkBusy.value) return
  const source = draft.value ?? editorDraft.value
  forkBusy.value = true
  forkRefusal.value = null
  let branch: string
  try {
    branch = (await ops.fork(name, props.branch)).branch
  } catch (refused) {
    forkRefusal.value = said(refused)
    forkBusy.value = false
    return
  }

  forking.value = false
  carryingDraftTo.value = branch
  conflict.value = false
  editingBase.value = null
  emit('view-branch', branch)
  await nextTick()

  try {
    const detail = await props.session.request('cells.show', {
      flow: props.session.path.value,
      branch,
      slug: slug.value,
    })
    await ops.edit(slug.value, source, { branch, base: detail.definition_hash })
    draft.value = null
    editorDraft.value = ''
    editing.value = false
    notice.value = `saved on ${branch}`
  } catch (refused) {
    draft.value = source
    editorDraft.value = source
    editing.value = true
    notice.value = said(refused)
  } finally {
    forkBusy.value = false
  }
}

async function land(source: string, options: { force?: boolean }): Promise<void> {
  draft.value = source
  const base = editingBase.value ?? live.base.value
  if (base === null) {
    notice.value = 'cell detail is still loading'
    return
  }
  // Optimistic only where the store is: the edit reads as pending until the
  // daemon has taken it, because until then it may still come back a conflict.
  notice.value = 'saving…'
  try {
    await ops.edit(slug.value, source, {
      branch: props.branch,
      base,
      force: options.force,
    })
    conflict.value = false
    draft.value = null
    editorDraft.value = ''
    editing.value = false
    editingBase.value = null
    notice.value = null
  } catch (refused) {
    if (refused instanceof FlowApiError && refused.kind === 'EditConflict') {
      conflict.value = true
      notice.value = refused.message
      return
    }
    // Stepped back from the change: the draft stays open, nothing to say.
    if (refused instanceof MoveCancelled) {
      editing.value = true
      notice.value = null
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
    if (refused instanceof MoveCancelled) return
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

async function onCopyContext(): Promise<void> {
  notice.value = 'copying context…'
  try {
    const built = await ops.copyContext(slug.value, props.branch)
    await navigator.clipboard.writeText(built.text)
    notice.value = 'context copied'
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
    if (props.branch === carryingDraftTo.value) {
      carryingDraftTo.value = null
      return
    }
    editorDraft.value = ''
    editing.value = false
  },
)
</script>
