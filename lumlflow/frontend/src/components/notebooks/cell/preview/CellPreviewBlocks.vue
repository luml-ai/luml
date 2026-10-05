<template>
  <div class="flex flex-col gap-3 nowheel nodrag">
    <section v-for="(section, index) in sections" :key="index" class="section">
      <header v-if="section.title || actionsOf(section, index).length" class="section-header">
        <span class="section-title">{{ section.title }}</span>
        <div class="section-actions">
          <Button
            v-if="clamped(section)"
            v-tooltip.top="'Expand'"
            variant="outlined"
            severity="secondary"
            class="section-action"
            aria-label="Expand"
            @click="onExpand"
          >
            <template #icon>
              <Maximize2 :size="14" />
            </template>
          </Button>
          <CellChartFilter
            v-if="filterable(section)"
            v-model:hidden="hiddenBySection[index]"
            :metrics="metricsOf(section)"
          />
        </div>
      </header>
      <CellChart
        v-if="section.kind === 'lines' || section.kind === 'bars'"
        :section="section"
        :hidden="hiddenBySection[index] ?? EMPTY"
      />
      <CellKeyValueBlock
        v-else-if="section.kind === 'kv'"
        :entries="section.entries"
        :limit="clamped(section) ? COMPACT_KV_ROWS : null"
      />
      <CellTableBlock v-else-if="section.kind === 'table'" :block="section.block" />
      <CellPlotImage v-else-if="section.kind === 'image'" :block="section.block" />
      <CellMarkdownBlock v-else-if="section.kind === 'markdown'" :block="section.block" />
      <CellFileBlock v-else :block="section.block" />
    </section>
    <p v-if="truncated" class="text-sm text-muted-color">Preview truncated.</p>
  </div>
</template>

<script setup lang="ts">
import type { CellPreviewBlocksProps } from './preview.interface'
import type { PreviewSection } from './preview.helpers'
import { computed, ref, watch } from 'vue'
import { Button } from 'primevue'
import { Maximize2 } from 'lucide-vue-next'
import { useFlowStore } from '@/store/flow'
import { chartColor } from '@/plotly/plotly.const'
import { COMPACT_KV_ROWS, hasChart, previewSections } from './preview.helpers'
import CellChart from './CellChart.vue'
import CellChartFilter from './CellChartFilter.vue'
import CellTableBlock from './CellTableBlock.vue'
import CellPlotImage from './CellPlotImage.vue'
import CellMarkdownBlock from './CellMarkdownBlock.vue'
import CellKeyValueBlock from './CellKeyValueBlock.vue'
import CellFileBlock from './CellFileBlock.vue'

const props = defineProps<CellPreviewBlocksProps>()

const flowStore = useFlowStore()

const EMPTY = new Set<number>()

const sections = computed(() => previewSections(props.blocks))
const withChart = computed(() => hasChart(sections.value))

/** Which metrics each chart leaves out, by section. */
const hiddenBySection = ref<Record<number, Set<number>>>({})
watch(
  () => props.blocks,
  () => {
    hiddenBySection.value = Object.fromEntries(
      sections.value.map((_, index) => [index, new Set<number>()]),
    )
  },
  { immediate: true },
)

function metricsOf(section: PreviewSection) {
  if (section.kind === 'lines') {
    return section.series.map((series, index) => ({ name: series.name, color: chartColor(index) }))
  }
  if (section.kind === 'bars') {
    return section.entries.map(([name], index) => ({ name, color: chartColor(index) }))
  }
  return []
}

/** A chart is worth filtering once it draws more than one metric. */
function filterable(section: PreviewSection): boolean {
  return metricsOf(section).length > 1
}

/**
 * On a card a long list of values gives way to the chart beside it: it shows
 * its first rows, and the rest is one click away in the expanded cell. With
 * no chart on the card the list keeps the room and shows what fits.
 */
function clamped(section: PreviewSection): boolean {
  return (
    !!props.compact &&
    withChart.value &&
    section.kind === 'kv' &&
    section.entries.length > COMPACT_KV_ROWS
  )
}

function actionsOf(section: PreviewSection, index: number): string[] {
  const actions: string[] = []
  if (clamped(section)) actions.push(`expand-${index}`)
  if (filterable(section)) actions.push(`filter-${index}`)
  return actions
}

function onExpand() {
  if (props.slug) flowStore.setExpandedCellId(props.slug)
}
</script>

<style scoped>
@reference "@/assets/css/index.css";

.section {
  @apply flex flex-col gap-2;
}
.section-header {
  @apply flex items-center justify-between gap-2 min-h-8;
}
.section-title {
  @apply text-sm font-medium truncate;
}
.section-actions {
  @apply flex items-center gap-1 shrink-0;
}
:deep(.section-action) {
  @apply w-8 h-8 p-0;
}
</style>
