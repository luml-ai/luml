<template>
  <div
    class="card"
    :class="{
      'card--running': live?.kind === 'running',
      'card--queued': live?.kind === 'queued',
      'card--agent': live?.kind === 'agent',
    }"
    :data-live="live?.kind ?? null"
  >
    <NotebookCellHeader :title="title" :icon="icon" :cost-seconds="costSeconds" :cell="cell" />
    <div v-if="live" class="live-strip" :class="`live-strip--${live.kind}`" role="status">
      <LoaderCircle v-if="live.kind !== 'queued'" :size="14" class="animate-spin shrink-0" />
      <Clock v-else :size="14" class="shrink-0" />
      <span class="truncate">{{ liveLabel }}</span>
    </div>
    <div class="py-4 live-body">
      <slot>
        <Accordion v-model:value="activePanels" multiple>
          <AccordionPanel value="code" :pt="ACCORDION_PANEL_PT">
            <AccordionHeader :pt="ACCORDION_HEADER_PT">Code</AccordionHeader>
            <AccordionContent :pt="ACCORDION_CONTENT_PT">
              <NotebookCode
                v-if="activePanels.includes('code')"
                :slug="cell.slug"
                :full-height="true"
              />
            </AccordionContent>
          </AccordionPanel>
          <AccordionPanel value="logs" :pt="ACCORDION_PANEL_PT">
            <AccordionHeader :pt="ACCORDION_HEADER_PT">Logs</AccordionHeader>
            <AccordionContent :pt="ACCORDION_CONTENT_PT">
              <NotebookLogs v-if="activePanels.includes('logs')" :slug="cell.slug" />
            </AccordionContent>
          </AccordionPanel>
          <AccordionPanel
            v-for="output in outputs"
            :key="output.name"
            :value="output.name"
            :pt="ACCORDION_PANEL_PT"
          >
            <AccordionHeader :pt="ACCORDION_HEADER_PT">{{ output.label }}</AccordionHeader>
            <AccordionContent :pt="ACCORDION_CONTENT_PT">
              <NotebookOutput
                v-if="activePanels.includes(output.name)"
                :slug="cell.slug"
                :name="output.name"
              />
            </AccordionContent>
          </AccordionPanel>
        </Accordion>
      </slot>
    </div>
    <NotebookCellFooter :state="state" :causes="causes" :reused="reused" :cell="cell" />
  </div>
</template>

<script setup lang="ts">
import type { NotebookCellProps } from '@/components/notebooks/cell/cell.interface'
import { computed, ref } from 'vue'
import { Accordion, AccordionContent, AccordionHeader, AccordionPanel } from 'primevue'
import { Clock, LoaderCircle } from 'lucide-vue-next'
import { useFlowStore } from '@/store/flow'
import { agentToolVerb } from '@/components/notebooks/cell/cell.const'
import {
  ACCORDION_CONTENT_PT,
  ACCORDION_HEADER_PT,
  ACCORDION_PANEL_PT,
} from '@/prime-vue/pass-through/accordion.pt'
import { capitalize } from '@/helpers/string'
import NotebookCellHeader from '@/components/notebooks/cell/NotebookCellHeader.vue'
import NotebookCellFooter from '@/components/notebooks/cell/NotebookCellFooter.vue'
import NotebookOutput from '@/components/notebooks/cell/NotebookOutput.vue'
import NotebookCode from '@/components/notebooks/cell/NotebookCode.vue'
import NotebookLogs from '@/components/notebooks/cell/NotebookLogs.vue'

const props = defineProps<NotebookCellProps>()

const flowStore = useFlowStore()

const activePanels = ref<string[]>(['code'])

// What is happening to this cell right now, as the daemon's live frames say:
// a run the kernel is inside of, one the queue holds, or a paired agent that
// has this cell — inside a call naming it, or between calls since one did.
// The stored state in the footer is what it was.
const live = computed(() => flowStore.cellLiveStates[props.cell.slug] ?? null)

const liveLabel = computed(() => {
  const state = live.value
  if (!state) return ''
  if (state.kind === 'running') return 'Running…'
  if (state.kind === 'queued') return 'Queued'
  if (state.inCall) return `${state.label} is ${agentToolVerb(state.tool)} this cell…`
  return `${state.label} is working on this cell`
})

const outputs = computed(() =>
  Object.keys(props.cell.kinds).map((name) => ({ name, label: capitalize(name) })),
)
</script>

<style scoped>
@reference "@/assets/css/index.css";

.card {
  @apply bg-(--p-card-background) border border-surface rounded-lg overflow-hidden p-5 shadow-(--p-card-shadow) relative transition-colors;
}
.card--running {
  @apply border-primary;
}
.card--running::before {
  /* A sweep along the top edge: the card is being computed on. */
  content: '';
  @apply absolute top-0 left-0 h-0.5 w-1/3 bg-primary rounded-full;
  animation: live-sweep 1.4s ease-in-out infinite;
}
.card--queued {
  @apply border-dashed;
}
.card--agent {
  @apply border-(--p-tag-info-color);
}
/* The agent has the cell: its body steps back until the call lands. */
.card--agent .live-body {
  @apply opacity-50 pointer-events-none select-none;
}
.card--running .live-body {
  @apply opacity-80;
}
.live-strip {
  @apply flex items-center gap-2 mt-3 px-3 py-1.5 rounded-md text-sm;
}
.live-strip--running {
  @apply bg-(--p-highlight-background) text-(--p-highlight-color);
}
.live-strip--queued {
  @apply bg-(--p-content-hover-background) text-muted-color;
}
.live-strip--agent {
  @apply bg-(--p-tag-info-background) text-(--p-tag-info-color);
}
@keyframes live-sweep {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(300%);
  }
}
</style>
