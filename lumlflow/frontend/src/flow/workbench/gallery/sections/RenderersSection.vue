<template>
  <div class="flex flex-col gap-12 max-w-4xl">
    <GallerySpecimen
      title="Frame"
      caption="PrimeVue DataTable at small size, dtype under every column header. The footer states the preview bound, so a preview never masquerades as the value."
    >
      <RendererHost :preview="framePreview" density="canvas" />
    </GallerySpecimen>

    <GallerySpecimen
      title="Dataset"
      caption="Head rows with the dtype under every column header, and a footer with the recorded row count and size, all from the stored preview and no kernel."
    >
      <RendererHost :preview="datasetPreview" density="canvas" />
    </GallerySpecimen>

    <GallerySpecimen
      title="Plot"
      caption="Inline SVG from stored series, with no chart library. A series may pin its own color (the chance diagonal here); the default palette reads in both themes."
    >
      <RendererHost :preview="plotPreview" density="canvas" />
    </GallerySpecimen>

    <GallerySpecimen
      title="Metric"
      caption="One formatter for the scalar, the direction arrow states which way is better, and the delta tag takes its color from whether it is an improvement, not from its sign."
    >
      <div class="flex flex-wrap gap-x-12 gap-y-4">
        <RendererHost :preview="metricPreview" density="canvas" />
        <RendererHost :preview="worseMetric" density="canvas" />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Note"
      caption="Markdown through marked + DOMPurify, styled by github-markdown-css: the app's one markdown pipeline."
    >
      <RendererHost :preview="notePreview" density="canvas" />
    </GallerySpecimen>

    <GallerySpecimen
      title="Model"
      caption="Headline metric, config grid, flavor and size. When the cell also produced an experiment, a quiet line points at that output instead of duplicating it."
    >
      <RendererHost :preview="modelPreview" density="canvas" />
    </GallerySpecimen>

    <GallerySpecimen
      title="Experiment"
      caption="Run name, main metric prominent, config as compact chips, curves as a mini SVG plot. The tracker ref renders as a plain anchor out to the experiment screen."
    >
      <RendererHost :preview="experimentPreview" density="canvas" />
    </GallerySpecimen>

    <GallerySpecimen
      title="Eval"
      caption="Score tiles in a grid; the footer names the dataset reference and sample count, because a score without its dataset is not a result."
    >
      <RendererHost :preview="evalPreview" density="canvas" />
    </GallerySpecimen>

    <GallerySpecimen
      title="File"
      caption="Checkpoints and other binary kinds: filename in mono, size, content type, and a download-style anchor. Nothing pretends to preview bytes it cannot."
    >
      <RendererHost :preview="checkpointPreview" density="canvas" />
    </GallerySpecimen>

    <GallerySpecimen
      title="Text"
      caption="Preformatted and clamped; the fade appears only when the text actually clips, so short values never get a washed-out last line."
    >
      <RendererHost :preview="logText" density="notebook" />
    </GallerySpecimen>

    <GallerySpecimen
      title="Key-value fallback"
      caption="The kind registry is open at runtime, so unknown kinds render the stored preview as a two-column grid, never an error. A newer preview format says so inline."
    >
      <div class="flex flex-col gap-6">
        <RendererHost :preview="kvPreview" density="canvas" />
        <RendererHost :preview="newerFormatKv" density="canvas" />
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Non-value states"
      caption="The five preview states, mirroring the @luml/attachments vocabulary: quiet, centered, one line each. A failure mode without a surface is a spinner that never resolves."
    >
      <div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <div
          v-for="state in shellStates"
          :key="state"
          class="rounded-lg border border-surface-200 dark:border-surface-700"
        >
          <p class="font-mono text-sm text-muted-color px-3 pt-2">{{ state }}</p>
          <PreviewShell :state="state" :detail="shellDetail(state)" />
        </div>
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Primary-output ranking"
      caption="train_model produces model, run, checkpoint, and curves. The experiment wins, so the card opens on the finding rather than a config dump."
    >
      <div class="flex flex-col gap-2">
        <div
          v-for="output in rankedOutputs"
          :key="output.name"
          class="flex items-center gap-3 text-base"
        >
          <KindBadge :kind="output.kind" icon-only />
          <code class="font-mono">{{ output.name }}</code>
          <span class="text-sm text-muted-color tabular-nums">rank {{ rankOf(output.kind) }}</span>
          <span v-if="output.name === primary?.name" class="text-sm text-primary font-medium">
            primary · opens first
          </span>
        </div>
      </div>
    </GallerySpecimen>

    <GallerySpecimen
      title="Density"
      caption="The same stored preview at two densities: bounded to ~220px on a canvas card, generous in the expand drawer. One renderer, one prop, so the views cannot drift apart."
    >
      <div class="grid lg:grid-cols-2 gap-4">
        <div class="flex flex-col gap-2 min-w-0">
          <p class="font-mono text-sm text-muted-color">density="canvas"</p>
          <div class="rounded-lg border border-surface-200 dark:border-surface-700 p-3">
            <RendererHost :preview="experimentPreview" density="canvas" />
          </div>
        </div>
        <div class="flex flex-col gap-2 min-w-0">
          <p class="font-mono text-sm text-muted-color">density="drawer"</p>
          <div class="rounded-lg border border-surface-200 dark:border-surface-700 p-3">
            <RendererHost :preview="experimentPreview" density="drawer" />
          </div>
        </div>
      </div>
    </GallerySpecimen>
  </div>
</template>

<script setup lang="ts">
import { mainCells, trainModel } from '../../fixtures'
import { primaryOutput, rankOf } from '../../model/registry'
import type {
  CellOutput,
  FlowCell,
  KvPreview,
  MetricPreview,
  PreviewValue,
  TextPreview,
} from '../../model/types'
import RendererHost from '../../renderers/RendererHost.vue'
import PreviewShell from '../../renderers/PreviewShell.vue'
import KindBadge from '../../ui/KindBadge.vue'
import GallerySpecimen from '../GallerySpecimen.vue'

function fixturePreview(slug: string, output: string): PreviewValue {
  const cell = mainCells.find((entry) => entry.slug === slug) as FlowCell
  return (cell.outputs.find((entry) => entry.name === output) as CellOutput).preview
}

const framePreview = fixturePreview('clean_data', 'clean')
const datasetPreview = fixturePreview('load_customers', 'customers')
const plotPreview = fixturePreview('roc_curve', 'roc')
const metricPreview = fixturePreview('holdout_eval', 'auc')
const notePreview = fixturePreview('summary', 'note')
const modelPreview = fixturePreview('train_model', 'model')
const experimentPreview = fixturePreview('train_model', 'run')
const evalPreview = fixturePreview('holdout_eval', 'eval')
const checkpointPreview = fixturePreview('train_model', 'checkpoint')
const kvPreview = fixturePreview('sweep_config', 'config')

// A regression on a higher-is-better metric: the tag goes red on a negative
// delta because it is a worsening, not because it is negative.
const worseMetric: MetricPreview = {
  ...(metricPreview as MetricPreview),
  value: 0.829,
  delta: -0.012,
}

const newerFormatKv: KvPreview = {
  ...(kvPreview as KvPreview),
  newerFormatNote: 'newer preview format. showing raw fields.',
}

const logText: TextPreview = {
  type: 'text',
  text: `[14:31:12] loading features.train_split (67,125 rows)
[14:31:14] xgboost 2.1.1 · tree_method=hist · device=cpu
[14:31:19] epoch 1/24 · train_loss 0.688 · val_auc 0.651
[14:31:31] epoch 2/24 · train_loss 0.612 · val_auc 0.702
[14:31:44] epoch 3/24 · train_loss 0.557 · val_auc 0.741
[14:31:56] epoch 4/24 · train_loss 0.521 · val_auc 0.768
[14:32:07] epoch 5/24 · train_loss 0.494 · val_auc 0.789
[14:32:19] epoch 6/24 · train_loss 0.473 · val_auc 0.803
[14:32:31] epoch 7/24 · train_loss 0.455 · val_auc 0.813
[14:32:44] epoch 8/24 · train_loss 0.441 · val_auc 0.821
[14:32:56] epoch 9/24 · train_loss 0.429 · val_auc 0.827
[14:33:08] epoch 10/24 · train_loss 0.419 · val_auc 0.831
[14:33:21] epoch 11/24 · train_loss 0.410 · val_auc 0.835
[14:33:33] epoch 12/24 · train_loss 0.403 · val_auc 0.837`,
}

const shellStates = ['loading', 'empty', 'too-big', 'error', 'unsupported'] as const

function shellDetail(state: (typeof shellStates)[number]): string | undefined {
  if (state === 'error') return "KeyError: 'p_churn'"
  if (state === 'too-big') return '38.2 MB · preview limit 8 MB'
  return undefined
}

const rankedOutputs = [...trainModel.outputs].sort((a, b) => rankOf(a.kind) - rankOf(b.kind))
const primary = primaryOutput(trainModel)
</script>
