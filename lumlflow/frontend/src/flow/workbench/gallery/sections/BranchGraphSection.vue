<template>
  <div class="flex flex-col gap-12 max-w-4xl">
    <GallerySpecimen
      title="The switcher"
      caption="The shortcut in the top bar: pick a lane and the whole screen re-scopes to it, which is a store read and a change of URL. Using a lane here is the other verb. It sits in the footer behind a sentence naming what it moves. A dropdown that rebound files while you browsed would make looking dangerous."
    >
      <BranchSwitcher
        :branches="branches"
        viewed-branch="exp/lr-1e3"
        worktree-branch="main"
        @view="onView"
        @checkout="onCheckout(false, $event)"
        @new-branch="onNewBranch"
      />
    </GallerySpecimen>

    <GallerySpecimen
      title="Naming a lane"
      caption="The parent is stated rather than picked: a lane starts from the one being viewed, which every other surface on the screen is already scoped to."
    >
      <Button label="New lane" outlined @click="forking = true">
        <template #icon>
          <Plus :size="14" />
        </template>
      </Button>
      <NewBranchDialog v-model:visible="forking" from="main" @create="onFork" />
    </GallerySpecimen>

    <GallerySpecimen
      title="The step timeline"
      caption="Where a lane moves through its own history: its steps newest first, the one it is on marked, every older one a rewind behind a confirm that names what it restores. Marking a point is the other half. The journal records every change, so what a checkpoint adds is a name for one of them."
    >
      <StepTimeline
        branch="main"
        :entries="steps"
        :head-step="23"
        checked-out
        @rewind="onRewind"
        @checkpoint="onCheckpoint"
      />
    </GallerySpecimen>

    <GallerySpecimen
      title="The lane map"
      caption="One row per lane, x is the journal step, a curve from the parent row at the step it started. Each row carries the newest state, last intent, headline metric, and who is on it. Archived lanes collapse behind the toggle."
    >
      <BranchGraph
        :branches="branches"
        @view="onView"
        @checkout="onCheckout(false, $event)"
        @archive="onArchive"
        @compare="onCompare"
      />
    </GallerySpecimen>

    <GallerySpecimen
      title="Selection mode"
      caption="Checkboxes join the verbs. One visit to the map both reads a lane and picks the ones to compare. The CTA arms at 2–5 selections and names the count."
    >
      <BranchGraph
        :branches="branches"
        selectable
        @view="onView"
        @checkout="onCheckout(false, $event)"
        @archive="onArchive"
        @compare="onCompare"
      />
    </GallerySpecimen>

    <GallerySpecimen
      title="Locked files"
      caption="View stays available for every lane, because it is a pure store read. Use-here waits while an agent holds the files: disabled with the reason, plus the labeled force escape."
    >
      <BranchGraph
        :branches="branches"
        worktree-locked
        @view="onView"
        @checkout="onCheckout(true, $event)"
        @archive="onArchive"
        @compare="onCompare"
      />
    </GallerySpecimen>

    <GallerySpecimen
      title="The overlay"
      caption="The map wrapped in a modal dialog: the disclosure behind the lane identifier. It is consulted at decision points, not watched."
    >
      <Button label="Open lane map" outlined @click="overlayVisible = true">
        <template #icon>
          <Split :size="14" />
        </template>
      </Button>
      <BranchGraphOverlay
        v-model:visible="overlayVisible"
        :branches="branches"
        :worktree-locked="true"
        @view="onView"
        @checkout="onCheckout(true, $event)"
        @archive="onArchive"
        @compare="onCompare"
      />
    </GallerySpecimen>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Button } from 'primevue'
import { Plus, Split } from 'lucide-vue-next'
import { useToast } from 'primevue/usetoast'
import BranchSwitcher from '../../components/branch/BranchSwitcher.vue'
import NewBranchDialog from '../../components/branch/NewBranchDialog.vue'
import StepTimeline from '../../components/branch/StepTimeline.vue'
import BranchGraph from '../../components/graph/BranchGraph.vue'
import BranchGraphOverlay from '../../components/graph/BranchGraphOverlay.vue'
import { branches, journal } from '../../fixtures'
import GallerySpecimen from '../GallerySpecimen.vue'

const toast = useToast()

const overlayVisible = ref(false)
const forking = ref(false)

/**
 * `main`'s own steps, plus a marked one — the timeline lists positions on one
 * branch, so the workspace-scoped lines the activity feed folds in are not
 * rows here: an env change is not somewhere this branch can be moved back to.
 */
const steps = computed(() => [
  {
    step: 24,
    time: '14:35',
    branch: 'main',
    actor: { kind: 'user' as const, label: 'user' },
    intent: 'before I rewrite the scorer',
    kind: 'checkpoint' as const,
    summary: '',
  },
  ...journal.filter((entry) => entry.branch === 'main'),
])

function onView(name: string): void {
  toast.add({
    severity: 'secondary',
    summary: 'view',
    detail: `would view \`${name}\`. a pure store read, no lock, no kernel.`,
    life: 2500,
  })
}

function onCheckout(locked: boolean, name: string): void {
  toast.add({
    severity: 'secondary',
    summary: 'use here',
    detail: locked
      ? `would use \`${name}\` here. it waits while the agent holds the files.`
      : `would use \`${name}\` here. it binds the flow files.`,
    life: 2500,
  })
}

function onArchive(name: string): void {
  toast.add({
    severity: 'secondary',
    summary: 'archive',
    detail: `would archive \`${name}\``,
    life: 2500,
  })
}

function onNewBranch(): void {
  forking.value = true
}

function onFork(name: string): void {
  forking.value = false
  toast.add({
    severity: 'secondary',
    summary: 'new lane',
    detail: `would start \`${name}\` from the newest version of the viewed lane`,
    life: 2500,
  })
}

function onRewind(step: number): void {
  toast.add({
    severity: 'secondary',
    summary: 'rewind',
    detail: `would restore \`main\` to step ${step}. nothing recomputes.`,
    life: 2500,
  })
}

function onCheckpoint(intent: string): void {
  toast.add({
    severity: 'secondary',
    summary: 'checkpoint',
    detail: `would mark this point: "${intent}"`,
    life: 2500,
  })
}

function onCompare(names: string[]): void {
  toast.add({
    severity: 'secondary',
    summary: 'compare',
    detail: `would compare ${names.map((name) => `\`${name}\``).join(' · ')}`,
    life: 2500,
  })
}
</script>
