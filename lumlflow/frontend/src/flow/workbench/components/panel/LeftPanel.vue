<template>
  <div class="flex h-full min-h-0 min-w-0 flex-col bg-surface-0 dark:bg-surface-900">
    <div class="flex flex-col gap-2 border-b border-surface-200 px-3 py-3 dark:border-surface-700">
      <BranchIdentifier
        v-if="branch"
        :branch="branch"
        :worktree-branch="session.worktreeBranch"
        :journal="onThisBranch"
        :busy="branchBusy"
        @open="emit('open-graph')"
        @new-branch="emit('new-branch')"
        @rewind="emit('rewind', $event)"
        @checkpoint="emit('checkpoint', $event)"
      />
      <AgentTaskLine
        :paired="session.paired"
        :viewed-branch="viewedBranch"
        :connect="connect"
        @pair="emit('pair')"
      />
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
              <Button
                class="self-start"
                label="Summarize lane"
                severity="secondary"
                text
                @click="emit('summarize-branch')"
              >
                <template #icon><Sparkles :size="14" /></template>
              </Button>
            </div>
          </AccordionContent>
        </AccordionPanel>

        <AccordionPanel value="packages">
          <AccordionHeader :pt="HEADER_PT">
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
          </AccordionHeader>
          <AccordionContent :pt="CONTENT_PT">
            <PackagesPanel
              :env="env"
              :busy="envBusy"
              @restart-kernel="emit('restart-kernel')"
              @add-packages="emit('add-packages', $event)"
              @remove-package="emit('remove-package', $event)"
            />
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
import { computed } from 'vue'
import { Accordion, AccordionContent, AccordionHeader, AccordionPanel, Button } from 'primevue'
import { Sparkles, TriangleAlert } from 'lucide-vue-next'
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
import BranchIdentifier from './BranchIdentifier.vue'
import InventoryRows, { type InventoryRow } from './InventoryRows.vue'
import PackagesPanel from './PackagesPanel.vue'
import PanelSettings from './PanelSettings.vue'

/**
 * The left panel, scoped to ONE viewed branch: identifier, current agent task,
 * the inventory lenses (all over the same cells — never a second store), and
 * the two settings that are real. Switching the viewed branch re-scopes all of
 * it.
 */
const props = defineProps<{
  branches: BranchInfo[]
  cells: FlowCell[]
  viewedBranch: string
  session: WorkbenchSession
  env: EnvState
  settings: FlowSettings
  journal: JournalEntry[]
  /** Head entries that landed while this browser was away — frozen by the page. */
  behind?: number
  /** An env op is in flight: uv is running and a second one would race it. */
  envBusy?: boolean
  /** A branch op is in flight — the timeline's verbs wait rather than race it. */
  branchBusy?: boolean
  /** The prompt that pairs an agent, once the daemon has answered for it. */
  connect?: string | null
}>()

const emit = defineEmits<{
  'open-graph': []
  'new-branch': []
  /** Move this branch back to a step it recorded — nothing recomputes. */
  rewind: [step: number]
  /** Mark this point under the user's own words. */
  checkpoint: [intent: string]
  pair: []
  'select-cell': [slug: string]
  'summarize-branch': []
  'update-settings': [settings: FlowSettings]
  'restart-kernel': []
  'add-packages': [packages: string[]]
  'remove-package': [name: string]
}>()

/**
 * Cells is the lens the reader came for; the rest are opened on demand — by the
 * reader, or by the page when the catch-up marker sends them to the journal.
 */
const open = defineModel<string[]>('open', { default: () => ['cells'] })

const ACCORDION_PT = { root: { class: 'text-base' } }
const HEADER_PT = { root: { class: 'px-3 py-2.5 text-base font-normal' } }
const CONTENT_PT = { content: { class: 'px-1.5 pb-3 pt-0' } }

const branch = computed(() => props.branches.find((b) => b.name === props.viewedBranch))

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
 * What the timeline navigates: the steps that landed *on* this branch. The
 * feed below folds in the workspace-scoped lines too, because an env change is
 * context for a branch — but it is not a place this branch can be moved back
 * to, so it is not a row in a list of positions.
 */
const onThisBranch = computed(() =>
  props.journal.filter((entry) => entry.branch === props.viewedBranch),
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
function lensRows(kind: 'experiment' | 'model' | 'dataset'): InventoryRow[] {
  return props.cells.flatMap((cell) =>
    cell.outputs
      .filter((output) => output.kind === kind)
      .map((output) => ({
        key: `${cell.slug}.${output.name}`,
        slug: cell.slug,
        kind,
        title: titleOf(cell, output),
        // Addresses are mono; a run's own name is prose the author chose.
        mono: output.preview.type !== 'experiment',
        detail: detailOf(output),
        // Reading outside the store is a fact about an input, and the badge
        // belongs to the lens that is about inputs.
        external: kind === 'dataset' && cell.externalInput,
      })),
  )
}

/** An experiment names its run; everything else is addressed as `slug.output`. */
function titleOf(cell: FlowCell, output: CellOutput): string {
  if (output.preview.type === 'experiment') return output.preview.runName
  return `${cell.slug}.${output.name}`
}

/** The headline number, when a preview has been read and carries one. */
function detailOf(output: CellOutput): string | undefined {
  const metric =
    output.preview.type === 'experiment'
      ? output.preview.mainMetric
      : output.preview.type === 'model'
        ? output.preview.headlineMetric
        : undefined
  return metric ? `${metric.name} ${formatMetric(metric.value)}` : undefined
}

const experimentRows = computed<InventoryRow[]>(() => lensRows('experiment'))

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
