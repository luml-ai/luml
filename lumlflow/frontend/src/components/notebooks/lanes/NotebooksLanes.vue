<template>
  <Accordion class="border-t border-surface">
    <AccordionPanel value="1" class="border-none!">
      <AccordionHeader class="bg-transparent!" :pt="ACCORDION_HEADER_PT">
        <div class="flex items-center gap-1 text-sm font-normal">
          <ListTree :size="14" color="var(--p-text-muted-color)" />
          <span class="text-color">Lanes</span>
          <span class="text-muted-color">({{ flowStore.branches.length }})</span>
        </div>
      </AccordionHeader>
      <AccordionContent :pt="ACCORDION_CONTENT_PT">
        <NotebookLanesList />
        <div class="buttons">
          <CreateNewLane />
          <!-- TODO: Add compare -->
        </div>
      </AccordionContent>
    </AccordionPanel>
  </Accordion>
</template>

<script setup lang="ts">
import { ListTree } from 'lucide-vue-next'
import { Accordion, AccordionContent, AccordionHeader, AccordionPanel } from 'primevue'
import { ACCORDION_CONTENT_PT, ACCORDION_HEADER_PT } from '@/prime-vue/pass-through/accordion.pt'
import { useFlowStore } from '@/store/flow'
import NotebookLanesList from './NotebookLanesList.vue'
import CreateNewLane from './CreateNewLane.vue'

const flowStore = useFlowStore()
</script>

<style scoped>
@reference "@/assets/css/index.css";

.buttons {
  @apply flex items-center justify-between gap-2;
}
</style>
