<template>
  <div class="flex flex-col gap-12 max-w-5xl">
    <GallerySpecimen
      title="One card, four output tabs"
      caption="A training cell producing {model, run, checkpoint, curves} is one card: four output tabs plus code and logs, opening on the experiment via the primary ranking rather than on a config dump."
    >
      <CellCard
        :cell="trainedModel"
        density="canvas"
        :preflight="evalPreflight"
        v-on="cardEvents(trainedModel, evalPreflight)"
      />
    </GallerySpecimen>

    <GallerySpecimen
      title="Same card, notebook density"
      caption="Same cell, code accented: the code tab is default-selected, the source sits open under the header with the primary output below, and paddings tighten. Same card, different accent."
    >
      <div class="max-w-2xl">
        <CellCard
          :cell="trainedModel"
          density="notebook"
          :preflight="evalPreflight"
          v-on="cardEvents(trainedModel, evalPreflight)"
        />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Card states"
      caption="The same cell across every status. Unmaterialized renders quiet and never as stale, because there is no baseline to have changed. Transitive staleness is subdued. Running takes the live console."
    >
      <div class="grid grid-cols-1 xl:grid-cols-2 gap-x-4 gap-y-5">
        <div
          v-for="variant in stateVariants"
          :key="variant.title"
          class="flex flex-col gap-1.5 min-w-0"
        >
          <p class="text-sm text-muted-color">{{ variant.title }}</p>
          <CellCard
            :cell="variant.cell"
            density="canvas"
            :preflight="cheapPreflight"
            v-on="cardEvents(variant.cell, cheapPreflight)"
          />
        </div>
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Not named yet"
      caption="A scaffolded cell owes a name, and owing one is not an error. The placeholder renders as the rename gesture: muted, italic, with the flag's own sentence in its tooltip. A warning row under the header would tell the author what they already know."
    >
      <div class="max-w-2xl">
        <CellCard :cell="placeholderCell" density="canvas" v-on="cardEvents(placeholderCell)" />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Note cell"
      caption="Notes are prose cards: rendered markdown body, no run or stop. Edit and provenance stay, because a note is a real versioned asset."
    >
      <div class="max-w-2xl">
        <CellCard :cell="noteCell" density="canvas" v-on="cardEvents(noteCell)" />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Unknown kind falls back"
      caption="The kind registry is open at runtime: an unregistered kind renders as a key-value grid over the stored preview, never an error."
    >
      <div class="max-w-2xl">
        <CellCard :cell="kvFallbackCell" density="canvas" v-on="cardEvents(kvFallbackCell)" />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="External input"
      caption="A cell reading outside the store is unmemoizable and carries the external badge. The panel groups it under inputs, honest about what the store cannot know."
    >
      <div class="max-w-2xl">
        <CellCard :cell="externalInputCell" density="canvas" v-on="cardEvents(externalInputCell)" />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Editing a cell"
      caption="What the code tab's edit gesture opens: Python highlighted in the house palette, line numbers, Tab and Shift-Tab for indentation with Escape to hand Tab back to the page, undo history and bracket matching. Locked beside it: the same surface with the caret taken away."
    >
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div class="flex flex-col gap-1.5 min-w-0">
          <p class="text-sm text-muted-color">editing</p>
          <SourceEditor v-model="editedSource" max-height="16rem" aria-label="train_model source" />
        </div>
        <div class="flex flex-col gap-1.5 min-w-0">
          <p class="text-sm text-muted-color">read-only</p>
          <SourceEditor
            :model-value="trainedModel.source"
            readonly
            max-height="16rem"
            aria-label="train_model source, read only"
          />
        </div>
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Provenance forms"
      caption="Authorship as recorded: agent, human, mixed hands, the mixed-editing uncertainty flag instead of a confident wrong name, and the folded repair history."
    >
      <div class="flex flex-col gap-2.5">
        <ProvenanceLine
          v-if="materializedCell.provenance"
          :provenance="materializedCell.provenance"
        />
        <ProvenanceLine v-if="userFailedCell.provenance" :provenance="userFailedCell.provenance" />
        <ProvenanceLine v-if="kvFallbackCell.provenance" :provenance="kvFallbackCell.provenance" />
        <ProvenanceLine
          v-if="uncertainAttributionCell.provenance"
          :provenance="uncertainAttributionCell.provenance"
        />
        <ProvenanceLine
          v-if="agentFailedCell.provenance"
          :provenance="agentFailedCell.provenance"
          :repaired-attempts="1"
        />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Pending projection"
      caption="While an agent session holds the files, a UI edit lands in the store and the write to files waits. The code tab says so instead of pretending the file changed."
    >
      <div class="max-w-2xl">
        <CellCard
          :cell="pendingProjectionCell"
          density="notebook"
          v-on="cardEvents(pendingProjectionCell)"
        />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Expand drawer"
      caption="The card expanded into a full-height right drawer: the selected output at drawer density, config, the kernel-paged value for frames, links out to the tracker, and materialize-and-download when the bytes were never persisted."
    >
      <div class="flex flex-wrap gap-3">
        <Button outlined label="open train_model expanded" @click="openDrawer(drawerTrainCell)">
          <template #icon><Maximize2 :size="14" /></template>
        </Button>
        <Button
          outlined
          severity="secondary"
          label="open features expanded (paged frame)"
          @click="openDrawer(drawerFeaturesCell)"
        >
          <template #icon><Maximize2 :size="14" /></template>
        </Button>
      </div>
    </GallerySpecimen>
  </div>

  <ExpandDrawer
    v-model:visible="drawerOpen"
    :cell="drawerCell"
    :kernel-started="false"
    :materialize-seconds="10"
  />
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Button } from 'primevue'
import { useToast } from 'primevue/usetoast'
import { Maximize2 } from 'lucide-vue-next'
import CellCard from '../../components/card/CellCard.vue'
import ExpandDrawer from '../../components/card/ExpandDrawer.vue'
import ProvenanceLine from '../../components/card/ProvenanceLine.vue'
import SourceEditor from '../../components/card/SourceEditor.vue'
import {
  agentFailedCell,
  cachedCell,
  cellWith,
  cheapPreflight,
  evalPreflight,
  externalInputCell,
  kvFallbackCell,
  mainCells,
  materializedCell,
  multiOutputCell,
  noteCell,
  olderEnvCell,
  pendingProjectionCell,
  placeholderCell,
  runningCell,
  staleDefinitionCell,
  staleParentCell,
  staleTransitiveCell,
  uncertainAttributionCell,
  unmaterializedCell,
  userFailedCell,
} from '../../fixtures'
import { formatCost, formatCount } from '../../model/format'
import type { FlowCell, Preflight } from '../../model/types'
import GallerySpecimen from '../GallerySpecimen.vue'

const toast = useToast()

function note(summary: string): void {
  toast.add({ severity: 'secondary', summary, life: 2600 })
}

// Gallery cards only acknowledge their emits — nothing runs.
function cardEvents(cell: FlowCell, preflight?: Preflight) {
  return {
    expand: () => note(`would expand \`${cell.slug}\` into the drawer`),
    run: ({ force }: { force: boolean }) => {
      const closure = preflight ?? cheapPreflight
      note(
        `would run \`${cell.slug}\` · ${formatCount(closure.recompute.length, 'cell')}, ~${formatCost(closure.totalSeconds)}${force ? ' · force (memo ignored)' : ''}`,
      )
    },
    stop: () => note(`would stop the run on \`${cell.slug}\``),
    rename: () => note(`would rename \`${cell.slug}\`. every reference rewires atomically.`),
    delete: () => note(`would remove \`${cell.slug}\` from this lane's selection`),
    duplicate: () => note(`would duplicate \`${cell.slug}\` · a new identity with no consumers`),
    'send-to-agent': (payload: string) =>
      note(`handoff payload built · ${formatCount(payload.split('\n').length, 'line')}`),
    'resolve-conflict': (choice: 'overwrite' | 'fork') =>
      note(
        choice === 'fork'
          ? 'would save this edit to a new lane'
          : 'would overwrite the newer version',
      ),
    edit: ({ source }: { source: string }) =>
      note(
        `would land a new version of \`${cell.slug}\` (${formatCount(source.split('\n').length, 'line')}) in the store`,
      ),
  }
}

// The multi-output scenario needs the finished card; the fixture keeps it running.
const trainedModel = cellWith(multiOutputCell, {
  status: 'materialized',
  stale: undefined,
  console: undefined,
  timing: { costSeconds: 312, finishedAgo: '4m ago' },
  logs: 'epoch 24/24 · train_loss 0.329 · val_auc 0.841\nlogged run churn-xgb-lr3e4 to the tracker\n',
})

const stateVariants: { title: string; cell: FlowCell }[] = [
  { title: 'materialized', cell: materializedCell },
  { title: 'cached', cell: cachedCell },
  { title: 'older env', cell: olderEnvCell },
  { title: 'running', cell: runningCell },
  { title: 'stale · definition', cell: staleDefinitionCell },
  { title: 'stale · parent', cell: staleParentCell },
  { title: 'stale · transitive', cell: staleTransitiveCell },
  { title: 'unmaterialized', cell: unmaterializedCell },
]

// Drawer demos: never-persisted checkpoint on the training cell, paged frame on features.
const drawerTrainCell = cellWith(trainedModel, {
  outputs: trainedModel.outputs.map((output) =>
    output.name === 'checkpoint' ? { ...output, neverPersisted: true } : output,
  ),
})

const drawerFeaturesCell = mainCells.find((cell) => cell.slug === 'features') as FlowCell

// The editor specimen is live — the gallery is where the surface is typed into.
const editedSource = ref(trainedModel.source)

const drawerOpen = ref(false)
const drawerCell = ref<FlowCell>(drawerTrainCell)

function openDrawer(cell: FlowCell): void {
  drawerCell.value = cell
  drawerOpen.value = true
}
</script>
