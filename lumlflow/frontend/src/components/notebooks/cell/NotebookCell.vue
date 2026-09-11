<template>
  <div class="card">
    <NotebookCellHeader :title="title" :icon="icon" :cost-seconds="costSeconds" :cell="cell" />
    <div class="py-4">
      <slot>
        <Accordion multiple>
          <AccordionPanel value="code" :pt="ACCORDION_PANEL_PT">
            <AccordionHeader :pt="ACCORDION_HEADER_PT">Code</AccordionHeader>
            <AccordionContent :pt="ACCORDION_CONTENT_PT">
              <NotebookCode />
            </AccordionContent>
          </AccordionPanel>
          <AccordionPanel value="logs" :pt="ACCORDION_PANEL_PT">
            <AccordionHeader :pt="ACCORDION_HEADER_PT">Logs</AccordionHeader>
            <AccordionContent :pt="ACCORDION_CONTENT_PT">
              <NotebookLogs :slug="cell.slug" />
            </AccordionContent>
          </AccordionPanel>
          <AccordionPanel value="plot" :pt="ACCORDION_PANEL_PT">
            <AccordionHeader :pt="ACCORDION_HEADER_PT">Plot</AccordionHeader>
            <AccordionContent :pt="ACCORDION_CONTENT_PT">
              <NotebookPlot />
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
import { Accordion, AccordionContent, AccordionHeader, AccordionPanel } from 'primevue'
import {
  ACCORDION_CONTENT_PT,
  ACCORDION_HEADER_PT,
  ACCORDION_PANEL_PT,
} from '@/prime-vue/pass-through/accordion.pt'
import NotebookCellHeader from '@/components/notebooks/cell/NotebookCellHeader.vue'
import NotebookCellFooter from '@/components/notebooks/cell/NotebookCellFooter.vue'
import NotebookPlot from '@/components/notebooks/cell/NotebookPlot.vue'
import NotebookCode from '@/components/notebooks/cell/NotebookCode.vue'
import NotebookLogs from '@/components/notebooks/cell/NotebookLogs.vue'

defineProps<NotebookCellProps>()
</script>

<style scoped>
@reference "@/assets/css/index.css";

.card {
  @apply bg-(--p-card-background) border border-surface rounded-lg overflow-hidden p-5 shadow-(--p-card-shadow);
}
</style>
