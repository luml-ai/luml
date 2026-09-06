<template>
  <Accordion class="border-t border-surface">
    <AccordionPanel value="1" class="border-none!">
      <AccordionHeader class="bg-transparent!" :pt="ACCORDION_HEADER_PT">
        <div class="flex items-center gap-1 text-sm font-normal">
          <ListTree :size="14" color="var(--p-text-muted-color)" />
          <span class="text-color">Lanes</span>
          <span class="text-muted-color">(4)</span>
        </div>
      </AccordionHeader>
      <AccordionContent :pt="ACCORDION_CONTENT_PT">
        <NotebookLanesList />
        <div class="buttons">
          <Button variant="text" class="px-2.5!">
            <Plus :size="14" />
            <span>New lane</span>
          </Button>
          <Button variant="text" class="px-2.5!">
            <span>Compare</span>
          </Button>
        </div>
      </AccordionContent>
    </AccordionPanel>
  </Accordion>
</template>

<script setup lang="ts">
import { ListTree, Plus } from 'lucide-vue-next'
import { Accordion, AccordionContent, AccordionHeader, AccordionPanel, Button } from 'primevue'
import { ACCORDION_CONTENT_PT, ACCORDION_HEADER_PT } from '@/prime-vue/pass-through/accordion.pt'
import NotebookLanesList from './NotebookLanesList.vue'
</script>

<style scoped>
@reference "@/assets/css/index.css";

.buttons {
  @apply flex items-center justify-between gap-2;
}
</style>
