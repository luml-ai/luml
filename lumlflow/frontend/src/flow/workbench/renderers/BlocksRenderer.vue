<template>
  <div v-if="preview.blocks.length" class="flex flex-col gap-3 min-w-0">
    <template v-for="(block, index) in preview.blocks" :key="index">
      <FrameRenderer v-if="block.block === 'table'" :preview="asFrame(block)" :density="density" />
      <MiniChart
        v-else-if="block.block === 'series'"
        kind="line"
        :series="[{ label: block.name, points: block.points }]"
        :height="chartHeight(density)"
      />
      <img
        v-else-if="block.block === 'image'"
        class="max-w-full self-start rounded-lg"
        :src="`data:${block.mime};base64,${block.data}`"
        alt=""
      />
      <NoteRenderer
        v-else-if="block.block === 'markdown'"
        :preview="{ type: 'note', markdown: block.text }"
        :density="density"
      />
      <ConfigGrid v-else-if="block.block === 'kv'" :config="block.entries" />
      <FileRenderer v-else :preview="asFile(block)" :density="density" />
    </template>

    <p v-if="preview.truncated" class="text-sm text-muted-color">
      preview shortened to fit. the stored value is larger than what is drawn here.
    </p>
  </div>
  <PreviewShell v-else :state="preview.pending ? 'loading' : 'empty'" />
</template>

<script setup lang="ts">
import type {
  BlocksPreview,
  FileBlock,
  FilePreview,
  FramePreview,
  TableBlock,
} from '../model/types'
import ConfigGrid from './ConfigGrid.vue'
import FileRenderer from './FileRenderer.vue'
import FrameRenderer from './FrameRenderer.vue'
import MiniChart from './MiniChart.vue'
import NoteRenderer from './NoteRenderer.vue'
import PreviewShell from './PreviewShell.vue'
import { chartHeight, type RenderDensity } from './shared'

/**
 * A stored preview, drawn as the primitives it is made of.
 *
 * Kinds compose blocks rather than shipping renderers, so this is the whole
 * live rendering path: an `experiment` is markdown headings over kv grids, a
 * `frame` is one table, a workspace plugin nobody here has heard of is
 * whichever of the six it chose. Each block maps onto a built renderer
 * unchanged — nothing is inferred back out of a payload, because the fields a
 * per-kind view wants (which metric leads, whether higher is better) are not
 * in it, and inventing them would be the card claiming what no run recorded.
 */
defineProps<{
  preview: BlocksPreview
  density?: RenderDensity
}>()

function asFrame(block: TableBlock): FramePreview {
  return {
    type: 'frame',
    columns: block.columns,
    dtypes: block.dtypes,
    rows: block.rows,
    totalRows: block.totalRows,
  }
}

function asFile(block: FileBlock): FilePreview {
  return {
    type: 'file',
    fileName: block.name,
    sizeBytes: block.size,
    contentType: block.contentType,
  }
}
</script>
