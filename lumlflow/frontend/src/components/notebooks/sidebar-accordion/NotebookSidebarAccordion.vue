<template>
  <Accordion :pt="ACCORDION_PT">
    <AccordionPanel
      v-for="item in list"
      :key="item.value"
      :value="item.value"
      :pt="ACCORDION_PANEL_PT"
    >
      <AccordionHeader :pt="ACCORDION_HEADER_PT">
        <div class="flex items-center gap-1 text-sm font-normal">
          <component :is="item.icon" :size="14" color="var(--p-text-muted-color)" />
          <span class="text-color">{{ item.label }}</span>
          <span v-if="item.count !== undefined" class="text-muted-color">({{ item.count }})</span>
        </div>
      </AccordionHeader>
      <AccordionContent :pt="ACCORDION_CONTENT_PT">
        <component :is="item.component" />
      </AccordionContent>
    </AccordionPanel>
  </Accordion>
</template>

<script setup lang="ts">
import {
  ACCORDION_CONTENT_PT,
  ACCORDION_HEADER_PT,
  ACCORDION_PANEL_PT,
  ACCORDION_PT,
} from '@/prime-vue/pass-through/accordion.pt'
import { FlaskConical, SquareCode, History, CircuitBoard } from 'lucide-vue-next'
import { Accordion, AccordionContent, AccordionHeader, AccordionPanel } from 'primevue'
import NotebookAccordionCells from './NotebookAccordionCells.vue'
import NotebookAccordionExperiments from '@/components/notebooks/sidebar-accordion/NotebookAccordionExperiments.vue'
import NotebookAccordionModels from '@/components/notebooks/sidebar-accordion/NotebookAccordionModels.vue'
import NotebookAccordionActivities from '@/components/notebooks/sidebar-accordion/NotebookAccordionActivities.vue'

const list = [
  {
    icon: SquareCode,
    label: 'Cells',
    value: 'cells',
    count: 10,
    component: NotebookAccordionCells,
  },
  {
    icon: FlaskConical,
    label: 'Experiments',
    value: 'experiments',
    count: 1,
    component: NotebookAccordionExperiments,
  },
  {
    icon: CircuitBoard,
    label: 'Models',
    value: 'models',
    count: 1,
    component: NotebookAccordionModels,
  },
  {
    icon: History,
    label: 'Activities',
    value: 'activities',
    component: NotebookAccordionActivities,
  },
]
</script>

<style scoped></style>
