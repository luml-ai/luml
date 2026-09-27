<template>
  <div class="flex h-full min-h-0 min-w-0 flex-col bg-surface-0 dark:bg-surface-900">
    <div class="flex flex-col gap-2 border-b border-surface-200 px-3 py-3 dark:border-surface-700">
      <BranchIdentifier
        v-if="branch"
        :branch="branch"
        :worktree-branch="session.worktreeBranch"
        :journal="onThisBranch"
        :children="children"
        :busy="branchBusy"
        @open="emit('open-graph')"
        @new-branch="emit('new-branch')"
        @rewind="emit('rewind', $event)"
        @checkpoint="(intent, step) => emit('checkpoint', intent, step)"
      />
      <AgentTaskLine :paired="session.paired" :viewed-branch="viewedBranch" @pair="emit('pair')" />
    </div>

    <!--
      One disclosure idiom for every section, and only the primary lens open: a
      panel whose content is 2.4× its own scroll area is a panel nobody reads.
      A lens with nothing on the branch is not rendered at all.
    -->
    <div class="min-h-0 flex-1 overflow-y-auto">
      <Accordion v-model:value="open" multiple lazy :pt="ACCORDION_PT">
        <AccordionPanel v-for="lens in lenses" :key="lens.value" :value="lens.value">
          <AccordionHeader :pt="HEADER_PT">
            <span class="flex min-w-0 items-center gap-2 text-base">
              {{ lens.value }}
              <span class="text-muted-color">{{ lens.rows.length }}</span>
            </span>
          </AccordionHeader>
          <AccordionContent :pt="CONTENT_PT">
            <InventoryRows :rows="lens.rows" @select="emit('select-cell', $event)" />
          </AccordionContent>
        </AccordionPanel>

        <AccordionPanel value="agents">
          <AccordionHeader :pt="HEADER_PT">
            <span class="flex min-w-0 items-center gap-2 text-base">
              agents
              <span v-if="agents.length" class="text-muted-color">{{ agents.length }}</span>
            </span>
          </AccordionHeader>
          <AccordionContent :pt="CONTENT_PT">
            <AgentsPanel
              :harnesses="agents"
              :loading="agentsLoading"
              :load-error="agentsError"
              :busy-ids="agentsBusy"
              @setup="onSetupAgents"
              @update="emit('update-agent', $event)"
              @remove="emit('remove-agent', $event)"
            />
          </AccordionContent>
        </AccordionPanel>

        <!--
          The one home for the journal. It was also a right-hand drawer over the
          canvas, opened by a button beside it — two mounts of one feed over one
          set of transactions, and the reader had to learn which was which.
        -->
        <AccordionPanel value="activity">
          <AccordionHeader :pt="HEADER_PT">
            <span class="flex min-w-0 items-center gap-2 text-base">
              activity
              <span v-if="session.changesBehind" class="text-(--p-primary-color)">
                {{ session.changesBehind }} new
              </span>
            </span>
          </AccordionHeader>
          <AccordionContent :pt="CONTENT_PT">
            <div class="flex flex-col gap-2">
              <!-- A marker, not an inbox: what landed while the reader was away
                   reads as one window rather than a queue to clear. -->
              <template v-if="sinceCursor.length">
                <p class="px-1.5 text-sm text-(--p-primary-color)">since you were here</p>
                <JournalFeed :entries="sinceCursor" />
                <div class="border-t border-surface-200 dark:border-surface-700" />
              </template>
              <JournalFeed v-if="beforeCursor.length" :entries="beforeCursor" />
              <p v-else-if="!sinceCursor.length" class="px-1.5 text-sm text-muted-color">
                nothing yet
              </p>
            </div>
          </AccordionContent>
        </AccordionPanel>

        <AccordionPanel value="packages">
          <AccordionHeader :pt="HEADER_PT">
            <span class="flex min-w-0 flex-1 flex-col items-start">
              <span class="flex min-w-0 items-center gap-2 text-base">
                packages
                <span class="text-muted-color">{{ env.packages.length }}</span>
                <TriangleAlert
                  v-if="env.mismatch"
                  v-tooltip.top="'The running kernel is behind the env'"
                  :size="14"
                  class="text-(--p-message-warn-color)"
                  aria-label="env mismatch"
                />
              </span>
              <span
                v-if="interpreterSentence"
                class="block max-w-full truncate font-mono text-xs text-muted-color"
                :title="interpreterSentence"
              >
                {{ interpreterSentence }}
              </span>
            </span>
          </AccordionHeader>
          <AccordionContent :pt="CONTENT_PT">
            <PackagesPanel :env="env" @restart-kernel="emit('restart-kernel')" />
          </AccordionContent>
        </AccordionPanel>

        <AccordionPanel value="settings">
          <AccordionHeader :pt="HEADER_PT">
            <span class="text-base">settings</span>
          </AccordionHeader>
          <AccordionContent :pt="CONTENT_PT">
            <PanelSettings :settings="settings" @update="emit('update-settings', $event)" />
          </AccordionContent>
        </AccordionPanel>
      </Accordion>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { Accordion, AccordionContent, AccordionHeader, AccordionPanel } from 'primevue'
import { TriangleAlert } from 'lucide-vue-next'
import type { AgentHarness } from '@/flow/api/types'
import { formatMetric } from '../../model/format'
import { primaryOutput } from '../../model/registry'
import type {
  BranchInfo,
  CellOutput,
  EnvState,
  FlowCell,
  FlowSettings,
  JournalEntry,
  WorkbenchSession,
} from '../../model/types'
import JournalFeed from '../session/JournalFeed.vue'
import AgentTaskLine from './AgentTaskLine.vue'
import AgentsPanel from './AgentsPanel.vue'
import BranchIdentifier from './BranchIdentifier.vue'
import InventoryRows, { type InventoryRow } from './InventoryRows.vue'
import PackagesPanel from './PackagesPanel.vue'
import PanelSettings from './PanelSettings.vue'

/**
 * The left panel, scoped to ONE viewed branch: identifier, current agent task,
 * the inventory lenses (all over the same cells — never a second store), and
 * the flow settings. Switching the viewed branch re-scopes all of it.
 */
const props = withDefaults(
  defineProps<{
    branches: BranchInfo[]
    cells: FlowCell[]
    viewedBranch: string
    session: WorkbenchSession
    env: EnvState
    settings: FlowSettings
    journal: JournalEntry[]
    agents?: AgentHarness[]
    agentsLoading?: boolean
    agentsError?: string | null
    agentsBusy?: string[]
    /** Head entries that landed while this browser was away — frozen by the page. */
    behind?: number
    /** A branch op is in flight — the timeline's verbs wait rather than race it. */
    branchBusy?: boolean
  }>(),
  {
    agents: () => [],
    agentsLoading: false,
    agentsError: null,
    agentsBusy: () => [],
  },
)

const emit = defineEmits<{
  'open-graph': []
  'new-branch': []
  /** Move this branch back to a step it recorded — nothing recomputes. */
  rewind: [step: number]
  /** Mark the current step under the user's own words. */
  checkpoint: [intent: string, step: number]
  pair: []
  'open-agents': []
  'setup-agents': [ids: string[], consent: boolean]
  'update-agent': [id: string]
  'remove-agent': [id: string]
  'select-cell': [slug: string]
  'update-settings': [settings: FlowSettings]
  'restart-kernel': []
}>()

/**
 * Cells is the lens the reader came for; the rest are opened on demand — by the
 * reader, or by the page when the catch-up marker sends them to the journal.
 */
const open = defineModel<string[]>('open', { default: () => ['cells'] })

watch(
  () => open.value.includes('agents'),
  (opened) => {
    if (opened) emit('open-agents')
  },
  { immediate: true },
)

function onSetupAgents(ids: string[], consent: boolean): void {
  emit('setup-agents', ids, consent)
}

const ACCORDION_PT = { root: { class: 'text-base' } }
const HEADER_PT = { root: { class: 'px-3 py-2.5 text-base font-normal' } }
const CONTENT_PT = { content: { class: 'px-1.5 pb-3 pt-0' } }

const branch = computed(() => props.branches.find((b) => b.name === props.viewedBranch))
const children = computed(() =>
  props.branches.filter((candidate) => candidate.parent === props.viewedBranch),
)

const interpreterSentence = computed(() => {
  const interpreter = props.env.interpreter
  if (!interpreter?.path) return ''
  const source =
    interpreter.source === 'lumlflow' ? "lumlflow's own interpreter" : interpreter.source
  return `python ${interpreter.path}${source ? ` · source ${source}` : ''}`
})

/**
 * The viewed branch's history — plus what happened to the workspace under all
 * of them. An env change or a helper edit carries no branch, and hiding it here
 * would drop the cause the staleness chips above are naming.
 */
function onBranch(entry: JournalEntry): boolean {
  return !entry.branch || entry.branch === props.viewedBranch
}

/**
 * Where the feed draws its line. The page freezes it: read live it would be
 * zero by the time the section painted — opening the section is what marks the
 * window seen — and the divider would never appear.
 */
const split = computed(() => props.behind ?? 0)

/** The window that landed while the reader was away, on this branch. */
const sinceCursor = computed(() => props.journal.slice(0, split.value).filter(onBranch))

const beforeCursor = computed(() => props.journal.slice(split.value).filter(onBranch))

/**
 * What the timeline navigates: the places on this branch — the steps that
 * changed what it selects. The feed below reads the whole history, this
 * branch's and the workspace's: an env change, a checkout, a note or a rewind
 * are context for the branch, not somewhere it can stand, so they are not rows
 * in a list of positions.
 */
const onThisBranch = computed(() =>
  props.journal.filter((entry) => entry.branch === props.viewedBranch && entry.position),
)

const cellRows = computed<InventoryRow[]>(() =>
  props.cells.map((cell) => ({
    key: cell.slug,
    slug: cell.slug,
    kind: primaryOutput(cell)?.kind ?? 'unknown',
    title: cell.slug,
    mono: true,
    status: cell.status,
    stale: cell.stale,
  })),
)

/**
 * The lenses group on the output's **kind**, which is what the cell declared
 * where it declared one of the four words. A preview says the same thing when
 * one has been read, but a lens that waited for previews would list nothing
 * until every card on the branch had fetched its payload.
 */
function lensRows(kind: 'model' | 'dataset'): InventoryRow[] {
  return props.cells.flatMap((cell) =>
    cell.outputs
      .filter((output) => output.kind === kind)
      .map((output) => ({
        key: `${cell.slug}.${output.name}`,
        slug: cell.slug,
        kind,
        title: `${cell.slug}.${output.name}`,
        mono: true,
        detail: detailOf(output),
        // Reading outside the store is a fact about an input, and the badge
        // belongs to the lens that is about inputs.
        external: kind === 'dataset' && cell.externalInput,
      })),
  )
}

/** The headline number, when a preview has been read and carries one. */
function detailOf(output: CellOutput): string | undefined {
  const metric = output.preview.type === 'model' ? output.preview.headlineMetric : undefined
  return metric ? `${metric.name} ${formatMetric(metric.value)}` : undefined
}

const experimentRows = computed<InventoryRow[]>(() =>
  props.cells.flatMap((cell) => {
    const tracker = cell.tracker
    const output = cell.outputs.find((candidate) => candidate.kind === 'experiment')
    if (!tracker || !output) return []
    return [
      {
        key: `${cell.slug}.${output.name}.${tracker.id}`,
        slug: cell.slug,
        kind: 'experiment' as const,
        title: `${cell.slug}.${output.name}`,
        mono: true,
        trackerState: tracker.state,
        tags: tracker.tags.slice(0, 1),
      },
    ]
  }),
)

const modelRows = computed<InventoryRow[]>(() => lensRows('model'))

/** Dataset outputs plus external-volatility cells — what "input" honestly means at runtime. */
const dataRows = computed<InventoryRow[]>(() => {
  const rows = lensRows('dataset')
  const listed = new Set(rows.map((row) => row.slug))
  for (const cell of props.cells) {
    if (!cell.externalInput || listed.has(cell.slug)) continue
    rows.push({
      key: cell.slug,
      slug: cell.slug,
      kind: primaryOutput(cell)?.kind ?? 'unknown',
      title: cell.slug,
      mono: true,
      external: true,
    })
  }
  return rows
})

const docRows = computed<InventoryRow[]>(() =>
  props.cells
    .filter((cell) => cell.isNote)
    .map((cell) => ({
      key: cell.slug,
      slug: cell.slug,
      kind: 'note' as const,
      title: noteTitle(cell),
    })),
)

/** A lens with nothing on this branch is not a section, it is a header saying zero. */
const lenses = computed(() =>
  [
    { value: 'cells', rows: cellRows.value },
    { value: 'experiments', rows: experimentRows.value },
    { value: 'models', rows: modelRows.value },
    { value: 'data', rows: dataRows.value },
    { value: 'docs', rows: docRows.value },
  ].filter((lens) => lens.rows.length > 0),
)

/** First markdown heading of the note, falling back to the slug. */
function noteTitle(cell: FlowCell): string {
  for (const output of cell.outputs) {
    if (output.preview.type !== 'note') continue
    const heading = output.preview.markdown
      .split('\n')
      .find((line) => line.trimStart().startsWith('#'))
    if (heading) return heading.replace(/^\s*#+\s*/, '')
  }
  return cell.slug
}
</script>
