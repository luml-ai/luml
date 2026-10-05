<template>
  <div
    class="card"
    :class="{
      'card--running': live?.kind === 'running',
      'card--queued': live?.kind === 'queued',
      'card--agent': live?.kind === 'agent' && live.active,
      'card--held': live?.kind === 'agent' && !live.active,
    }"
    :data-live="live?.kind ?? null"
    :style="live?.kind === 'agent' ? { '--agent-color': live.color } : undefined"
  >
    <NotebookCellHeader :title="title" :icon="icon" :cost-seconds="costSeconds" :cell="cell" />
    <div
      v-if="live?.kind === 'agent' && !live.active"
      class="held-note"
      role="status"
      :title="lockHint"
    >
      <Lock :size="12" class="shrink-0" />
      <span class="truncate">Held by {{ live.label }}</span>
    </div>
    <div
      v-else-if="live"
      class="live-strip"
      :class="`live-strip--${live.kind}`"
      role="status"
      :title="lockHint"
    >
      <LoaderCircle
        v-if="live.kind === 'running' || (live.kind === 'agent' && live.inCall)"
        :size="14"
        class="animate-spin shrink-0"
      />
      <Lock v-else-if="live.kind === 'agent'" :size="14" class="shrink-0" />
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
import { Clock, LoaderCircle, Lock } from 'lucide-vue-next'
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
// holds this cell — the daemon refuses it to every other agent meanwhile.
// The stored state in the footer is what it was.
const live = computed(() => flowStore.cellLiveStates[props.cell.slug] ?? null)

const liveLabel = computed(() => {
  const state = live.value
  if (!state) return ''
  if (state.kind === 'running') return 'Running…'
  if (state.kind === 'queued') return 'Queued'
  if (state.inCall && state.tool) {
    return `${state.label} is ${agentToolVerb(state.tool)} this cell…`
  }
  return `${state.label} is working on this cell`
})

// A held cell is closed to every other agent, and the strip says until when.
const lockHint = computed(() => {
  const state = live.value
  if (state?.kind !== 'agent') return undefined
  return `Other agents can't change or run this cell until ${state.label} moves to another cell, disconnects, or leaves it alone for ${Math.round(flowStore.claimIdleMinutes)} minutes.`
})

const outputs = computed(() =>
  Object.keys(props.cell.kinds).map((name) => ({ name, label: capitalize(name) })),
)
</script>

<style scoped>
@reference "@/assets/css/index.css";

.card {
  @apply bg-(--p-card-background) border border-surface rounded-lg overflow-hidden p-5 shadow-(--p-card-shadow) relative transition-colors flex flex-col;
}
/* A card given a height cap keeps its header and footer, and its body shows
   as much as fits between them. */
.live-body {
  @apply min-h-0 flex-1 overflow-hidden;
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
  border-color: var(--agent-color);
}
/* The agent is at work on the cell: its body steps back, but stays yours to
   click — an agent's hold never closes a cell to a person. */
.card--agent .live-body {
  @apply opacity-60;
}
/* Held, not worked on: a thin line in the agent's colour, nothing dimmed. */
.card--held {
  border-color: color-mix(in srgb, var(--agent-color) 45%, var(--p-content-border-color));
}
.held-note {
  @apply flex items-center gap-1.5 mt-2 text-xs text-muted-color;
}
.held-note :deep(svg) {
  color: var(--agent-color);
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
  color: var(--agent-color);
  background: color-mix(in srgb, var(--agent-color) 12%, transparent);
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
