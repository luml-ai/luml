<template>
  <article
    class="rounded-lg border bg-surface-0 dark:bg-surface-900 flex flex-col min-w-0"
    :class="[
      loudError
        ? 'border-(--p-message-error-border-color)'
        : 'border-surface-200 dark:border-surface-700',
      selected ? 'ring-2 ring-primary-500' : '',
    ]"
  >
    <header class="flex flex-col gap-1.5" :class="headerPad">
      <div class="flex items-start gap-2.5 min-w-0">
        <div class="flex items-center gap-x-2.5 gap-y-1 flex-wrap min-w-0 flex-1">
          <!--
            A cell that has not been named yet is not a cell doing something
            wrong: `untitled_1` is the state every cell is created in. So the
            name says so by being unfinished — muted, italic, and the rename
            gesture itself — instead of a warning row under the header telling
            the author what they already know about the cell they just made.
          -->
          <h3 v-if="unnamed" class="min-w-0">
            <Button
              v-tooltip.top="cell.flag!.message"
              text
              severity="secondary"
              :aria-label="`name this cell. ${cell.slug} is a placeholder.`"
              :pt="NAME_PT"
              @click="emit('rename')"
            >
              <span class="font-mono font-semibold italic" :class="titleSize">{{ cell.slug }}</span>
              <Pencil :size="14" class="shrink-0" />
            </Button>
          </h3>
          <h3
            v-else
            class="font-mono font-semibold transition-colors duration-500"
            :class="[titleSize, cell.renamedFrom ? 'text-primary-600 dark:text-primary-400' : '']"
          >
            {{ cell.slug }}
          </h3>
          <!-- A rename is the same cell under a new name, and saying so is what
               keeps it from reading as one card gone and another arrived. -->
          <span
            v-if="cell.renamedFrom"
            class="text-sm text-muted-color transition-opacity duration-500"
          >
            renamed from <code class="font-mono">{{ cell.renamedFrom }}</code>
          </span>
          <KindBadge v-if="primary" :kind="primary.kind" icon-only :icon-size="14" />
          <!-- Only deviations are chipped: `materialized` is the ordinary case,
               and cached/older-env are facts about the timing beside it. -->
          <StatusChip
            v-if="cell.status !== 'materialized'"
            :status="cell.status"
            :stale="cell.stale"
          />
          <MetaBadge v-if="cell.externalInput" variant="external" />
        </div>
        <div v-if="timingLine" class="shrink-0 pt-0.5 text-right text-sm text-muted-color">
          {{ timingLine }}
        </div>
      </div>
      <!-- Said once: the code tab has the docstring in the source, and an output
           on screen says more about the cell than a sentence about it does. -->
      <p
        v-if="cell.doc && !selectedOutput && activeTab !== 'code'"
        class="text-sm text-muted-color"
      >
        {{ cell.doc }}
      </p>
    </header>

    <div class="flex flex-col" :class="bodyPad">
      <!--
        Only a declaration nobody can act on gets the warn field. A hygiene flag
        is a normalization the runtime already applied — a fact, stated once and
        quietly — and a placeholder name is carried by the header above.
      -->
      <Message v-if="loudFlag" severity="warn" size="small">
        <template #icon><TriangleAlert :size="14" class="shrink-0" /></template>
        <div class="flex w-full flex-wrap items-center gap-2">
          <span class="min-w-40 flex-1 text-sm" v-html="flagHtml" />
          <Button
            v-if="cell.flag!.didYouMean"
            text
            severity="warn"
            label="apply suggestion"
            @click="applySuggestion"
          />
        </div>
      </Message>
      <p v-else-if="quietFlag" class="text-sm text-muted-color" v-html="flagHtml" />

      <!--
        Reactivity is on and it is leaving this one alone. Quiet, because it is
        not a fault: the alternative is silence, which is what made a cell the
        threshold declined look exactly like a cell the runtime had forgotten.
      -->
      <p v-if="autoLine" class="flex items-start gap-1.5 text-sm text-muted-color">
        <ZapOff :size="14" class="mt-0.5 shrink-0" />
        <span>{{ autoLine }}</span>
      </p>

      <ConflictMenu v-if="cell.conflict" @resolve="emit('resolve-conflict', $event)" />

      <Message v-if="loudError" severity="error" size="small">
        <template #icon><CircleAlert :size="14" class="shrink-0" /></template>
        <div class="flex w-full flex-wrap items-center gap-2">
          <code class="min-w-40 flex-1 font-mono text-sm">{{ cell.error!.summary }}</code>
          <SendToAgentButton
            :cell="cell"
            :branch="branchName"
            gesture="fix"
            label="Fix this"
            severity="danger"
            :handoff="handoffFor('fix')"
            @open="emit('handoff', $event)"
            @send-to-agent="emit('send-to-agent', $event)"
          />
        </div>
      </Message>

      <CellTabStrip :tabs="tabs" :selected="activeTab" @select="selectedTab = $event" />

      <div class="min-w-0">
        <template v-if="selectedOutput">
          <div
            v-if="cell.status === 'unmaterialized'"
            class="rounded-lg border border-dashed border-surface-200 dark:border-surface-700 px-3 py-6 text-center text-sm text-muted-color"
          >
            not materialized on this lane
          </div>
          <div v-else class="overflow-auto" :class="density === 'canvas' ? 'max-h-72' : 'max-h-80'">
            <RendererHost :preview="selectedOutput.preview" :density="density" />
          </div>
        </template>
        <CodeView
          v-else-if="activeTab === 'code'"
          :cell="cell"
          :density="density"
          @edit="emit('edit', $event)"
          @edit-start="emit('edit-start')"
        />
        <ConsoleView v-else-if="activeTab === 'console'" :lines="cell.console ?? []" />
        <LogsView v-else-if="activeTab === 'logs'" :logs="cell.logs" :error="cell.error" />

        <!-- Demoted agent failure, notebook density only: code is the subject, so
             the summary may sit under it — quiet, no red wash. -->
        <p
          v-if="quietError && activeTab === 'code'"
          class="mt-2 border-l-2 border-(--p-message-error-border-color) pl-2 font-mono text-sm text-muted-color"
        >
          {{ cell.error!.summary }}
        </p>

        <!-- Notebook accent: source open under the header, outputs below. -->
        <!-- The tab above already names the output; a label row would say it twice. -->
        <div
          v-if="density === 'notebook' && activeTab === 'code' && primary && !cell.isNote"
          class="mt-3 max-h-64 overflow-auto border-t border-surface-200 pt-2.5 dark:border-surface-700"
        >
          <RendererHost :preview="primary.preview" density="notebook" />
        </div>
      </div>
    </div>

    <footer class="flex flex-wrap items-center justify-between gap-3" :class="footerPad">
      <ProvenanceLine
        v-if="cell.provenance"
        :provenance="cell.provenance"
        :repaired-attempts="cell.error?.repairedAttempts"
        class="flex-1 min-w-0"
      />
      <span v-else class="flex-1" />
      <CellOpRow
        :cell="cell"
        :density="density"
        :awaiters="awaiters"
        :preflight="preflight"
        :branch="branchName"
        :handoff="handoffFor('explain')"
        @run="emit('run', $event)"
        @preflight="emit('preflight')"
        @stop="emit('stop')"
        @expand="emit('expand')"
        @handoff="emit('handoff', $event)"
        @send-to-agent="emit('send-to-agent', $event)"
        @rename="emit('rename')"
        @delete="emit('delete')"
        @duplicate="emit('duplicate')"
        @add-downstream="emit('add-downstream')"
        @promote="emit('promote')"
        @eager="emit('eager', $event)"
      />
    </footer>
  </article>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Button, Message } from 'primevue'
import { CircleAlert, Pencil, TriangleAlert, ZapOff } from 'lucide-vue-next'
import type { HandoffGesture } from '@/flow/api/types'
import { formatCost } from '../../model/format'
import { primaryOutput } from '../../model/registry'
import type { FlowCell, Preflight } from '../../model/types'
import KindBadge from '../../ui/KindBadge.vue'
import MetaBadge from '../../ui/MetaBadge.vue'
import StatusChip from '../../ui/StatusChip.vue'
import RendererHost from '../../renderers/RendererHost.vue'
import SendToAgentButton from '../handoff/SendToAgentButton.vue'
import CellOpRow from './CellOpRow.vue'
import CellTabStrip, { type CellTab } from './CellTabStrip.vue'
import CodeView from './CodeView.vue'
import ConflictMenu from './ConflictMenu.vue'
import ConsoleView from './ConsoleView.vue'
import LogsView from './LogsView.vue'
import ProvenanceLine from './ProvenanceLine.vue'
import { inlineCodeHtml } from './inlineCode'

/**
 * One card per cell — the product's central component. A tab strip over the
 * assets the cell produced plus code and logs, at two densities: canvas leads
 * with outputs, notebook leads with code. Same card, different accent.
 */
const props = defineProps<{
  cell: FlowCell
  density: 'canvas' | 'notebook'
  selected?: boolean
  /** Demo-only: other branches awaiting the in-flight run (drives stop wording). */
  awaiters?: number
  /** The daemon-served run closure; null while it is still being asked for. */
  preflight?: Preflight | null
  /** Branch context for handoff payloads; the design system defaults to main. */
  branch?: string
  /**
   * The daemon's handoff payload and which gesture asked for it. Absent leaves
   * both buttons on the locally built payload, which is the fixture mode.
   */
  handoff?: { gesture: HandoffGesture; text: string } | null
}>()

const emit = defineEmits<{
  /** Which tab is on screen — what a live card pulls its payload for. */
  tab: [id: string]
  expand: []
  run: [payload: { force: boolean }]
  /** The run closure is wanted; the daemon computes it, so it is asked for. */
  preflight: []
  stop: []
  rename: []
  delete: []
  duplicate: []
  'add-downstream': []
  promote: []
  eager: [on: boolean]
  /** A handoff popover opened — the gesture to go and build a payload for. */
  handoff: [gesture: HandoffGesture]
  'send-to-agent': [payload: string]
  'resolve-conflict': [choice: 'overwrite' | 'fork']
  edit: [payload: { source: string }]
  /** The editor opened — where the version an edit is based on gets pinned. */
  'edit-start': []
}>()

const branchName = computed(() => props.branch ?? 'main')

/** One payload is in hand at a time, and it belongs to the gesture that asked. */
function handoffFor(gesture: HandoffGesture): string | null {
  return props.handoff?.gesture === gesture ? props.handoff.text : null
}

const titleSize = computed(() => (props.density === 'canvas' ? 'text-lg' : 'text-base'))

/** The unnamed title is a button that has to sit where the `h3` sat. */
const NAME_PT = { root: { class: 'gap-1.5 p-0 text-muted-color hover:bg-transparent!' } }

const headerPad = computed(() => (props.density === 'canvas' ? 'px-4 pt-4' : 'px-4 pt-3.5'))
const bodyPad = computed(() =>
  props.density === 'canvas' ? 'px-4 pb-4 pt-3 gap-3.5' : 'px-4 pb-3.5 pt-2.5 gap-3',
)
const footerPad = computed(() => (props.density === 'canvas' ? 'px-4 py-2.5' : 'px-4 py-2'))

const primary = computed(() => primaryOutput(props.cell))

/**
 * One line for everything the run recorded about its own cost. `cached` and
 * `older env` were badges beside the status chip; they are facts about this
 * timing, and a header carrying four chips reads as an alert.
 */
const timingLine = computed(() => {
  const timing = props.cell.timing
  if (!timing) return ''
  const parts: string[] = []
  if (timing.costSeconds !== undefined) {
    parts.push(`${props.cell.status === 'running' ? '~' : ''}${formatCost(timing.costSeconds)}`)
  }
  if (timing.cached) parts.push('cached')
  if (timing.olderEnv) parts.push('older env')
  if (timing.finishedAgo) parts.push(timing.finishedAgo)
  return parts.join(' · ')
})

/**
 * What reactivity decided not to do, in words.
 *
 * Every case here names the way out, because the decision is only useful
 * next to the gesture that resolves it: the run button is right there, and a
 * cell that has never been timed stops being declined the moment it is run
 * once.
 */
const autoLine = computed(() => {
  const declined = props.cell.autoDeclined
  if (!declined) return ''
  if (declined.reason === 'blocked') {
    return 'waiting on a failed cell above it. reactivity retries after the next edit.'
  }
  if (declined.reason === 'never-timed') {
    return 'never run here, so its cost is unknown. run it once and it keeps itself fresh.'
  }
  return `too expensive to refresh on its own (~${formatCost(declined.estimateSeconds)}). run it when you want it.`
})

// --- errors: authorship decides the volume --------------------------------

const loudError = computed(() => props.cell.error?.author === 'user')
const quietError = computed(
  () => props.cell.error?.author === 'agent' && props.density === 'notebook',
)

// --- flag: three volumes, and the code is what picks one -------------------

/** The name is owed, not wrong. The header renders it as the rename gesture. */
const unnamed = computed(() => props.cell.flag?.code === 'placeholder_slug')

/** A normalization already applied — reported, never raised. */
const quietFlag = computed(() => props.cell.flag?.code === 'hygiene')

const loudFlag = computed(() => Boolean(props.cell.flag) && !unnamed.value && !quietFlag.value)

const flagHtml = computed(() => {
  const flag = props.cell.flag
  if (!flag) return ''
  const suffix = flag.didYouMean ? `. did you mean \`${flag.didYouMean}\`?` : ''
  return inlineCodeHtml(flag.message + suffix)
})

function applySuggestion(): void {
  const flag = props.cell.flag
  if (!flag?.didYouMean) return
  const broken = flag.message.match(/`([^`]+)`/)?.[1]
  const source = broken ? props.cell.source.split(broken).join(flag.didYouMean) : props.cell.source
  emit('edit', { source })
}

// --- tabs -----------------------------------------------------------------

const tabs = computed<CellTab[]>(() => {
  const list: CellTab[] = props.cell.outputs.map((output) => ({
    id: `out:${output.name}`,
    label: output.name,
    kind: output.kind,
  }))
  list.push({ id: 'code', label: 'code', icon: 'code' })
  if (props.cell.status === 'running')
    list.push({ id: 'console', label: 'console', icon: 'console', live: true })
  if (!props.cell.isNote) list.push({ id: 'logs', label: 'logs', icon: 'logs' })
  return list
})

function defaultTab(): string {
  if (props.cell.status === 'running') return 'console'
  const first = primary.value
  if (props.density === 'notebook' && first?.kind !== 'note') return 'code'
  return first ? `out:${first.name}` : 'code'
}

const selectedTab = ref(defaultTab())

// The live console takes focus the moment a run starts; a vanished tab
// (console after completion, a renamed output) falls back to the default.
watch(
  () => [props.cell.slug, props.cell.status, props.density] as const,
  ([, status], [, previousStatus]) => {
    if (status === 'running' && previousStatus !== 'running') selectedTab.value = 'console'
  },
)

const activeTab = computed(() =>
  tabs.value.some((tab) => tab.id === selectedTab.value) ? selectedTab.value : defaultTab(),
)

// Announced rather than kept private: a live card fetches the preview, source
// or log artifact behind the tab on screen, and pulling all of them for every
// card on a canvas is what this saves.
watch(activeTab, (id) => emit('tab', id), { immediate: true })

const selectedOutput = computed(() => {
  if (!activeTab.value.startsWith('out:')) return undefined
  const name = activeTab.value.slice(4)
  return props.cell.outputs.find((output) => output.name === name)
})
</script>
