<template>
  <div class="flex flex-col gap-12 max-w-5xl">
    <GallerySpecimen
      title="Demoted agent failure"
      caption="Agent-authored → demoted, not suppressed: the chip goes failed and the traceback fills logs, with no toast and no red wash. Notebook density may show the summary quietly under the code, because code is the subject. History folds to “v3→v4 · 1 failed attempt”."
    >
      <div class="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div class="flex flex-col gap-1.5 min-w-0">
          <p class="text-sm text-muted-color">canvas density</p>
          <CellCard :cell="agentFailedCell" density="canvas" v-on="cardEvents(agentFailedCell)" />
        </div>
        <div class="flex flex-col gap-1.5 min-w-0">
          <p class="text-sm text-muted-color">notebook density</p>
          <CellCard :cell="agentFailedCell" density="notebook" v-on="cardEvents(agentFailedCell)" />
        </div>
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Loud user failure"
      caption="User-authored → loud: inline error summary on the card, the full traceback in logs, and a Fix-this handoff preloaded with the error. That is the difference between showing an error and doing something about it."
    >
      <div class="max-w-2xl">
        <CellCard :cell="userFailedCell" density="canvas" v-on="cardEvents(userFailedCell)" />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Flagged reference with did-you-mean"
      caption="A broken declaration is accepted but flagged, never rejected, because agents iterate through broken intermediate states. The suggestion is one click away."
    >
      <div class="max-w-2xl">
        <CellCard :cell="flaggedCell" density="canvas" v-on="cardEvents(flaggedCell)" />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Conflict · the edit is based on an older version"
      caption="Optimistic locking rejected the edit into a menu. Save-to-a-new-lane is promoted because it loses nothing. Overwrite is secondary."
    >
      <div class="max-w-2xl">
        <CellCard :cell="conflictCell" density="canvas" v-on="cardEvents(conflictCell)" />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Agent session ended"
      caption="A persistent inline banner, a state rather than a toast, anchored under the last cell the agent touched. It says what is outstanding, never why the session ended, and offers the handoff payload."
    >
      <AgentEndedBanner
        :cell="agentFailedCell"
        branch="main"
        failed-run
        :unsynced-assets="2"
        @send-to-agent="
          (payload: string) =>
            note(`handoff payload built · ${formatCount(payload.split('\n').length, 'line')}`)
        "
      />
    </GallerySpecimen>

    <GallerySpecimen
      title="Kernel death"
      caption="Names the cell that was materializing when the kernel died, offers restart, and states what is true: nothing recorded is lost, and the queue is drained rather than silently retried."
    >
      <KernelDeathBanner
        slug="train_model"
        cause="out of memory"
        @restart-kernel="note('would restart the kernel under this lane\'s lock')"
      />
    </GallerySpecimen>
  </div>
</template>

<script setup lang="ts">
import { useToast } from 'primevue/usetoast'
import AgentEndedBanner from '../../components/card/AgentEndedBanner.vue'
import CellCard from '../../components/card/CellCard.vue'
import KernelDeathBanner from '../../components/card/KernelDeathBanner.vue'
import {
  agentFailedCell,
  cheapPreflight,
  conflictCell,
  flaggedCell,
  userFailedCell,
} from '../../fixtures'
import { formatCost, formatCount } from '../../model/format'
import type { FlowCell } from '../../model/types'
import GallerySpecimen from '../GallerySpecimen.vue'

const toast = useToast()

function note(summary: string): void {
  toast.add({ severity: 'secondary', summary, life: 2600 })
}

function cardEvents(cell: FlowCell) {
  return {
    expand: () => note(`would expand \`${cell.slug}\` into the drawer`),
    run: ({ force }: { force: boolean }) =>
      note(
        `would run \`${cell.slug}\` · ${formatCount(cheapPreflight.recompute.length, 'cell')}, ~${formatCost(cheapPreflight.totalSeconds)}${force ? ' · force (memo ignored)' : ''}`,
      ),
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
</script>
