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
      <ConfigGrid
        v-else-if="block.block === 'kv'"
        :config="block.entries"
        :metrics="preview.kind === 'metric'"
      />
      <FileRenderer
        v-else
        :preview="asFile(block)"
        :density="density"
        :download-url="downloadUrl"
      />
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

defineProps<{
  preview: BlocksPreview
  density?: RenderDensity
  downloadUrl?: string
}>()

function asFrame(block: TableBlock): FramePreview {
  return {
    type: 'frame',
    columns: block.columns,
    dtypes: block.dtypes,
    rows: block.rows,
    totalRows: block.totalRows,
    totalColumns: block.totalColumns,
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
