<template>
  <Dialog v-model:visible="visible" :pt="dialogPt" position="right" :draggable="false">
    <template #header>
      <div class="flex items-center gap-2">
        <component :is="headerIcon" :size="20" color="var(--p-primary-color)" />
        <h3 class="font-mono">{{ cell.slug }}</h3>
      </div>
    </template>
    <template #closeicon>
      <X :size="14" />
    </template>

    <div class="flex flex-col gap-7 pb-2">
      <CellTabStrip :tabs="outputTabs" :selected="activeTab" @select="selectedTab = $event" />

      <div
        class="rounded-lg border border-surface-200 dark:border-surface-700 p-3 overflow-auto max-h-[26rem]"
      >
        <RendererHost v-if="paged" :preview="paged" density="drawer" />
        <RendererHost
          v-else-if="selectedOutput"
          :preview="selectedOutput.preview"
          density="drawer"
          :download-url="selectedOutput.downloadUrl"
        />
      </div>

      <div v-if="pagedTotalRows !== null" class="flex flex-col gap-1.5">
        <div class="flex items-center gap-2 flex-wrap">
          <Button
            text
            rounded
            severity="secondary"
            size="small"
            aria-label="previous page"
            :disabled="paging || offset === 0"
            @click="emit('page', { output: outputName, move: 'previous' })"
          >
            <template #icon><ChevronLeft :size="14" /></template>
          </Button>
          <span class="text-sm text-muted-color">
            rows {{ (offset + 1).toLocaleString('en-US') }}–{{
              shownThrough.toLocaleString('en-US')
            }}
            of {{ pagedTotalRows.toLocaleString('en-US') }} ·
            {{ page ? 'kernel' : 'preview' }}
          </span>
          <Button
            text
            rounded
            severity="secondary"
            size="small"
            aria-label="next page"
            :disabled="paging || shownThrough >= pagedTotalRows"
            @click="emit('page', { output: outputName, move: 'next' })"
          >
            <template #icon><ChevronRight :size="14" /></template>
          </Button>
        </div>
        <p
          v-if="!kernelStarted"
          class="flex items-center gap-1.5 text-sm text-(--p-message-info-color)"
        >
          <Info :size="14" class="shrink-0" />
          expanding starts the kernel
        </p>
      </div>

      <div v-if="configEntries.length" class="flex flex-col gap-1.5">
        <p class="text-sm text-muted-color">config</p>
        <div class="grid grid-cols-[minmax(7rem,auto)_1fr] gap-x-4 gap-y-1 text-sm">
          <template v-for="[key, value] in configEntries" :key="key">
            <span class="font-mono text-muted-color">{{ key }}</span>
            <span class="font-mono">{{ value }}</span>
          </template>
        </div>
      </div>

      <div v-if="tracker" class="flex flex-col items-start gap-1.5 text-sm">
        <div class="inline-flex items-center gap-2">
          <TrackerStateBadge
            v-if="!tracker.url && selectedOutput?.preview.type !== 'experiment'"
            :state="tracker.state"
          />
          <RouterLink
            v-if="tracker.url"
            :to="tracker.url"
            class="inline-flex items-center gap-1.5 text-base text-primary hover:underline"
          >
            <ExternalLink :size="14" />
            open in Experiments
          </RouterLink>
          <TrackerUploadLink
            v-if="tracker.url && tracker.state === 'ok'"
            :experiment-id="tracker.id"
          />
        </div>
        <p v-if="trackerStateLine" class="text-muted-color">{{ trackerStateLine }}</p>
      </div>

      <div v-if="!isExperiment" class="flex flex-col gap-1.5">
        <div class="flex items-center gap-2.5 flex-wrap">
          <a
            v-if="downloadUrl && !needsRun"
            class="inline-flex items-center gap-2 rounded-md border border-primary px-3 py-2 text-sm text-primary hover:bg-primary/5"
            :href="downloadUrl"
            download
          >
            <Download :size="14" />
            download
          </a>
          <Button
            v-else-if="!selectedOutput?.neverPersisted"
            outlined
            :label="downloadLabel"
            :disabled="downloading"
            @click="emit('download', { output: outputName, materialize: needsRun })"
          >
            <template #icon><Download :size="14" /></template>
          </Button>
          <ModelUploadLink
            v-if="publishModel && selectedOutput?.declared === 'model' && downloadUrl && !needsRun"
            :publish="(target) => publishModel!(outputName, target)"
            :default-name="`${cell.slug}.${outputName}`"
          />
          <p v-if="selectedOutput?.neverPersisted" class="text-sm text-muted-color">
            declared not to persist. nothing stored to download.
          </p>
          <p v-else-if="needsRun" class="text-sm text-muted-color">
            downloading materializes it first
          </p>
        </div>
        <p v-if="notice" class="text-sm text-muted-color">{{ notice }}</p>
      </div>

      <div class="flex flex-col gap-1.5">
        <p class="text-sm text-muted-color">logs</p>
        <pre
          v-if="renderedLogs"
          class="font-mono text-sm leading-relaxed rounded-lg border border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800 p-3 overflow-auto max-h-48 whitespace-pre-wrap"
          >{{ renderedLogs }}</pre
        >
        <p v-else class="text-sm text-muted-color">no logs</p>
      </div>
    </div>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { Button, Dialog, type DialogPassThroughOptions } from 'primevue'
import { ChevronLeft, ChevronRight, Download, ExternalLink, Info, X } from 'lucide-vue-next'
import { formatCost } from '../../model/format'
import { primaryOutput } from '../../model/registry'
import { terminalText } from '@/utils/terminal'
import type { FlowCell, FramePreview, ParamValue, ValuePage } from '../../model/types'
import { KIND_ICONS } from '../../ui/kinds'
import TrackerStateBadge from '../../ui/TrackerStateBadge.vue'
import RendererHost from '../../renderers/RendererHost.vue'
import CellTabStrip, { type CellTab } from './CellTabStrip.vue'
import TrackerUploadLink from '../../ui/TrackerUploadLink.vue'
import ModelUploadLink from '../../ui/ModelUploadLink.vue'
import type { PublishTarget } from '@/components/upload/upload.interface'

const props = defineProps<{
  cell: FlowCell
  kernelStarted?: boolean
  materializeSeconds?: number
  page?: ValuePage | null
  paging?: boolean
  downloading?: boolean
  notice?: string | null
  publishModel?: (output: string, target: PublishTarget) => Promise<{ job_id: string }>
}>()

const emit = defineEmits<{
  page: [request: { output: string; move: 'first' | 'next' | 'previous' }]
  download: [request: { output: string; materialize: boolean }]
  tab: [output: string]
}>()

const visible = defineModel<boolean>('visible', { default: false })

const dialogPt: DialogPassThroughOptions = {
  mask: { class: 'pt-22 pb-8 px-4' },
  root: { class: 'w-full max-w-[44rem] h-full max-h-full! m-0!' },
  header: { class: 'text-xl font-medium' },
}

const primary = computed(() => primaryOutput(props.cell))

const headerIcon = computed(() => KIND_ICONS[primary.value?.kind ?? 'unknown'])

const outputTabs = computed<CellTab[]>(() =>
  props.cell.outputs.map((output) => ({
    id: `out:${output.name}`,
    label: output.name,
    kind: output.kind,
  })),
)

const selectedTab = ref('')

// Opening is what resets to the primary output. Closing must not: the emit
// below would then report a tab the card face is not showing, and the card
// fetches what it is told is on screen.
// Sources element-wise rather than a getter returning a fresh array: a live
// card rebuilds its model on every payload that lands, and a watcher comparing
// two new arrays fires each time — which would drag the reader back to the
// primary output whenever anything else finished loading.
watch(
  [() => props.cell.slug, visible],
  ([, open]) => {
    if (open) selectedTab.value = primary.value ? `out:${primary.value.name}` : ''
  },
  { immediate: true },
)

const activeTab = computed(() =>
  outputTabs.value.some((tab) => tab.id === selectedTab.value)
    ? selectedTab.value
    : (outputTabs.value[0]?.id ?? ''),
)

const selectedOutput = computed(() =>
  props.cell.outputs.find((output) => `out:${output.name}` === activeTab.value),
)

const outputName = computed(() => selectedOutput.value?.name ?? '')
const downloadUrl = computed(() => selectedOutput.value?.downloadUrl)

watch([visible, outputName], ([open, name]) => open && name && emit('tab', name), {
  immediate: true,
})

const paged = computed<FramePreview | null>(() => {
  const page = props.page
  if (!page) return null
  return {
    type: 'frame',
    columns: page.columns,
    dtypes: page.dtypes,
    rows: page.rows,
    totalRows: page.totalRows,
    totalColumns: page.totalColumns,
  }
})

const offset = computed(() => props.page?.offset ?? 0)
const shownThrough = computed(() => offset.value + (props.page?.rows.length ?? headRows.value))

const headRows = computed(() => {
  const preview = selectedOutput.value?.preview
  if (preview?.type === 'frame' || preview?.type === 'dataset') {
    return preview.type === 'frame' ? preview.rows.length : preview.head.length
  }
  if (preview?.type === 'blocks') {
    const table = preview.blocks.find((block) => block.block === 'table')
    return table ? table.rows.length : 0
  }
  return 0
})

const pagedTotalRows = computed<number | null>(() => {
  if (props.page) return props.page.totalRows
  const preview = selectedOutput.value?.preview
  if (preview?.type === 'frame' || preview?.type === 'dataset') return preview.totalRows
  if (preview?.type === 'blocks') {
    const table = preview.blocks.find((block) => block.block === 'table')
    return table ? table.totalRows : null
  }
  return null
})

watch(
  [visible, outputName, pagedTotalRows],
  ([open, name, total]) => {
    if (open && name && total !== null && !props.page && total > headRows.value) {
      emit('page', { output: name, move: 'first' })
    }
  },
  { immediate: true },
)

const configEntries = computed<[string, string][]>(() => {
  const merged = new Map<string, ParamValue>()
  const preview = selectedOutput.value?.preview
  if (preview?.type === 'model' || preview?.type === 'experiment') {
    for (const [key, value] of Object.entries(preview.config)) merged.set(key, value)
  }
  for (const [key, value] of Object.entries(props.cell.params)) merged.set(key, value)
  return [...merged.entries()].map(([key, value]) => [
    key,
    typeof value === 'string' ? value : JSON.stringify(value),
  ])
})

const isExperiment = computed(
  () =>
    selectedOutput.value?.kind === 'experiment' ||
    selectedOutput.value?.preview.type === 'experiment',
)

const tracker = computed(() => {
  if (!isExperiment.value) return undefined
  const preview = selectedOutput.value?.preview
  return preview?.type === 'experiment'
    ? (preview.tracker ?? props.cell.tracker)
    : props.cell.tracker
})

const trackerStateLine = computed(() => {
  const tracked = tracker.value
  if (!tracked || tracked.state === 'ok') return ''
  if (tracked.state === 'missing') {
    const recorded = tracked.recorded_step
      ? `the numbers below are what it recorded at step ${tracked.recorded_step}`
      : 'the numbers below are what it recorded'
    return `${recorded}. run ${props.cell.slug} to record it again.`
  }
  return tracked.sentence
})

const renderedLogs = computed(() => terminalText(props.cell.logs ?? '').trimEnd())

const needsRun = computed(
  () => !selectedOutput.value?.neverPersisted && props.cell.status === 'unmaterialized',
)

const downloadLabel = computed(() => {
  if (!needsRun.value) return 'download'
  const seconds = props.materializeSeconds ?? props.cell.timing?.costSeconds
  return seconds === undefined
    ? 'materialize and download'
    : `materialize and download · ~${formatCost(seconds)}`
})
</script>
