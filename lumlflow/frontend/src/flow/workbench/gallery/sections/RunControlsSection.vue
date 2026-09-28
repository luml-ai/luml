<template>
  <div class="flex flex-col gap-12 max-w-4xl">
    <GallerySpecimen
      title="Preflight · expensive closure"
      caption="Run never happens blind: with features stale, running holdout_eval names three recomputes and the total seconds before the click."
    >
      <PreflightPopover
        :preflight="evalPreflight"
        target="holdout_eval"
        label="run holdout_eval"
        @run="acknowledgeRun('holdout_eval', evalPreflight, $event)"
      />
    </GallerySpecimen>

    <GallerySpecimen
      title="Preflight · cheap closure"
      caption="A one-cell closure gets the same treatment: what is cached, what recomputes, the total. The shape never changes with the cost."
    >
      <PreflightPopover
        :preflight="cheapPreflight"
        target="roc_curve"
        label="run roc_curve"
        @run="acknowledgeRun('roc_curve', cheapPreflight, $event)"
      />
    </GallerySpecimen>

    <GallerySpecimen
      title="Rerun the whole lane"
      caption="Rerun-the-session means run this lane's slice to its leaves, under one preflight for the batch."
    >
      <div
        class="flex items-center justify-between gap-3 flex-wrap rounded-lg border border-surface-200 dark:border-surface-700 px-3 py-2"
      >
        <span class="text-base text-muted-color">
          rerun <code class="font-mono text-base">main</code> · runs the slice to every leaf
        </span>
        <PreflightPopover
          :preflight="branchPreflight"
          target="main · every leaf"
          label="rerun lane"
          @run="acknowledgeRun('main (lane)', branchPreflight, $event)"
        />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Force-rerun is a modifier"
      caption="Ignore-memo-hits is a labeled checkbox inside every preflight, never the default. Ticking it moves the cached cells into the run and leaves the total open-ended."
    >
      <PreflightPopover
        :preflight="evalPreflight"
        target="holdout_eval"
        label="run with the modifier visible"
        @run="acknowledgeRun('holdout_eval', evalPreflight, $event)"
      />
    </GallerySpecimen>

    <GallerySpecimen
      title="Stop · awaiter-aware wording"
      caption="An in-flight run may have several awaiting lanes. Preemption fires only when no awaiter still wants the result. The stop button says which case it is."
    >
      <div class="flex flex-col gap-3">
        <div class="flex items-center justify-between gap-4 flex-wrap">
          <span class="text-sm text-muted-color">no other lane waits → “stop the run”</span>
          <CellOpRow :cell="runningCell" density="canvas" :awaiters="0" v-on="opEvents(0)" />
        </div>
        <div class="flex items-center justify-between gap-4 flex-wrap">
          <span class="text-sm text-muted-color">
            2 other lanes wait → “leave the run, requeue this lane”
          </span>
          <CellOpRow :cell="runningCell" density="canvas" :awaiters="2" v-on="opEvents(2)" />
        </div>
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Stop the session"
      caption="The button only claims what lumlflow owns. Stopping the agent is not ours unless we own its process, and in v1 we do not."
    >
      <div class="flex flex-col gap-1.5">
        <Button
          severity="danger"
          outlined
          label="stop the session"
          class="self-start"
          @click="note('would cancel the in-flight run and drain the queue')"
        >
          <template #icon><OctagonX :size="14" /></template>
        </Button>
        <p class="text-sm text-muted-color">
          cancels runs and drains the queue. stopping the agent happens in its terminal.
        </p>
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Per-asset eager toggle"
      caption="Reactivity ships on auto, which refreshes a closure it has already timed under the threshold. Eager is the per-asset way past that threshold: an opt-in on one card, never a global switch that would auto-run training."
    >
      <div class="flex items-center gap-3 flex-wrap">
        <code class="font-mono text-base">roc_curve</code>
        <ToggleSwitch
          v-model="eagerDemo"
          :aria-label="'eager materialization for roc_curve'"
          @change="
            note(eagerDemo ? 'would set roc_curve to eager' : 'would set roc_curve back to lazy')
          "
        />
        <span class="text-sm text-muted-color">
          eager · rematerializes on change regardless of cost
        </span>
      </div>
    </GallerySpecimen>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Button, ToggleSwitch } from 'primevue'
import { useToast } from 'primevue/usetoast'
import { OctagonX } from 'lucide-vue-next'
import CellOpRow from '../../components/card/CellOpRow.vue'
import PreflightPopover from '../../components/card/PreflightPopover.vue'
import { cheapPreflight, evalPreflight, runningCell } from '../../fixtures'
import { formatCost, formatCount } from '../../model/format'
import type { Preflight } from '../../model/types'
import GallerySpecimen from '../GallerySpecimen.vue'

const toast = useToast()

function note(summary: string): void {
  toast.add({ severity: 'secondary', summary, life: 2600 })
}

function acknowledgeRun(target: string, preflight: Preflight, payload: { force: boolean }): void {
  note(
    `would run \`${target}\` · ${formatCount(preflight.recompute.length, 'cell')}, ~${formatCost(preflight.totalSeconds)}${payload.force ? ' · force (memo ignored)' : ''}`,
  )
}

function opEvents(awaiters: number) {
  return {
    run: (payload: { force: boolean }) => acknowledgeRun('roc_curve', cheapPreflight, payload),
    stop: () =>
      note(
        awaiters === 0
          ? 'would stop the run'
          : `would leave the run for ${formatCount(awaiters, 'awaiting lane')} and requeue this lane`,
      ),
    expand: () => note('would expand into the drawer'),
    'copy-context': () => note('would copy cell context'),
    rename: () => note('would rename. every reference rewires atomically.'),
    delete: () => note("would remove from this lane's selection"),
    duplicate: () => note('would duplicate · a new identity with no consumers'),
  }
}

// One preflight for the whole-branch rerun: everything below the stale edit.
const branchPreflight: Preflight = {
  cached: ['load_customers', 'clean_data', 'sweep_config'],
  recompute: ['features', 'train_model', 'holdout_eval', 'roc_curve', 'error_analysis'],
  unknown: ['error_analysis'],
  totalSeconds: 342.2,
  reasons: [],
}

const eagerDemo = ref(false)
</script>
