<template>
  <div class="flex max-w-5xl flex-col gap-12">
    <GallerySpecimen
      title="Integrity warning"
      caption="Comparability is never assumed. Divergent pins, mismatched datasets and mismatched scoring surface inline, and they name the affected lanes."
    >
      <div class="flex flex-col gap-3">
        <IntegrityWarningBar :warning="sweepCompare.warnings[0]" />
        <IntegrityWarningBar :warning="scoringMismatch" />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Result columns"
      caption="One column per lane, aligned on asset. The best value per score row carries a mark. The shared metric overlays on one chart, one color per lane."
    >
      <ResultColumns :compare="twoBranchCompare" />
    </GallerySpecimen>

    <GallerySpecimen
      title="Definition divergence"
      caption="The point where the lanes split: someone edited the cell. It is rare and structural. One side per distinct definition, with the differing param highlighted."
    >
      <DivergencePointCard :divergence="sweepCompare.definitionDivergences[0]" />
    </GallerySpecimen>

    <GallerySpecimen
      title="Materialization divergence"
      caption="Same code, different inputs. It is transitively closed, so it collapses to one row per asset with a chip per lane, never a fan of identical-code nodes."
    >
      <div class="flex flex-col gap-4">
        <MaterializationRows :rows="sweepCompare.materializationRows" />
        <div class="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm text-muted-color">
          <Tag severity="secondary" value="same" :pt="LEGEND_PT" />
          <Tag severity="success" value="better" :pt="LEGEND_PT" />
          <Tag severity="danger" value="worse" :pt="LEGEND_PT" />
          <Tag severity="secondary" value="missing" :pt="LEGEND_PT" class="opacity-60" />
          <span>state colors relative to the comparison baseline</span>
        </div>
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Shapeless differences"
      caption="Renames, absences, and param-only changes get an exhaustive plain table, so nothing is unreachable just because it did not fit the visual."
    >
      <ShapelessTable :differences="sweepCompare.shapelessDifferences" />
    </GallerySpecimen>

    <GallerySpecimen
      title="Experiments"
      caption="Each lane's tracked experiment links to Experiments while it is available and keeps its state badge when it is not."
    >
      <ArtifactLinks :links="sweepCompare.trackerLinks" />
    </GallerySpecimen>

    <GallerySpecimen
      title="Adopt & export"
      caption="The two closing verbs: adopt the winner's version of an asset (per-asset, with three-way conflict detection) and export the chosen slice as a file."
    >
      <AdoptBar winner="exp/lr-1e3" asset="train_model" target="main" />
    </GallerySpecimen>
  </div>
</template>

<script setup lang="ts">
import { Tag } from 'primevue'
import AdoptBar from '../../components/compare/AdoptBar.vue'
import ArtifactLinks from '../../components/compare/ArtifactLinks.vue'
import DivergencePointCard from '../../components/compare/DivergencePointCard.vue'
import IntegrityWarningBar from '../../components/compare/IntegrityWarningBar.vue'
import MaterializationRows from '../../components/compare/MaterializationRows.vue'
import ResultColumns from '../../components/compare/ResultColumns.vue'
import ShapelessTable from '../../components/compare/ShapelessTable.vue'
import { sweepCompare } from '../../fixtures/compare'
import type { CompareView, CompareWarning } from '../../model/types'
import GallerySpecimen from '../GallerySpecimen.vue'

const LEGEND_PT = { root: { class: 'px-2 py-0 text-sm font-normal' } }

// Two-lane slice of the sweep, warnings dropped: they have their own specimen.
const twoBranchCompare: CompareView = {
  ...sweepCompare,
  branches: sweepCompare.branches.slice(0, 2),
  warnings: [],
}

const scoringMismatch: CompareWarning = {
  kind: 'scoring-mismatch',
  message:
    '`holdout_eval` scores with weighted accuracy on exp/feature-drop but plain accuracy on main',
  affectedBranches: ['main', 'exp/feature-drop'],
}
</script>
