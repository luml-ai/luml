<template>
  <Accordion class="border-t border-surface">
    <AccordionPanel value="1" class="border-none!">
      <AccordionHeader class="bg-transparent!" :pt="ACCORDION_HEADER_PT">
        <div class="header">
          <History :size="14" color="var(--p-text-muted-color)" />
          <span class="text-color">Steps ({{ flowStore.currentBranchSteps.length }})</span>
        </div>
      </AccordionHeader>
      <AccordionContent :pt="ACCORDION_CONTENT_PT">
        <NotebookLanesCreatePoint />
        <p v-if="!flowStore.currentBranchSteps.length" class="empty">Nothing on this lane yet</p>
        <ol v-else class="steps">
          <li v-for="step in flowStore.currentBranchSteps" :key="step.step" class="step">
            <Flag
              v-if="flowStore.currentBranchPoints.has(step.step)"
              :size="14"
              class="point-icon"
            />
            <div class="step-info">
              <div class="step-title">
                <span class="step-intent">
                  {{ flowStore.currentBranchPoints.get(step.step) ?? step.intent }}
                </span>
              </div>
              <div v-if="flowStore.currentBranchPoints.has(step.step)" class="step-point-intent">
                {{ step.intent }}
              </div>
              <div class="step-meta">
                step {{ step.step }} · {{ formatUpdatedAgo(step.ts) }} · {{ step.actor }}
              </div>
            </div>
            <Tag
              v-if="step.step === flowStore.currentHeadStep"
              value="current"
              severity="secondary"
            />
            <Button
              v-else
              label="Go"
              severity="secondary"
              variant="outlined"
              size="small"
              :loading="rewindingStep === step.step"
              :disabled="rewindingStep !== null"
              @click="rewind(step.step)"
            />
          </li>
        </ol>
      </AccordionContent>
    </AccordionPanel>
  </Accordion>
</template>

<script setup lang="ts">
import { Accordion, AccordionContent, AccordionHeader, AccordionPanel, Button, Tag } from 'primevue'
import { Flag, History } from 'lucide-vue-next'
import { ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import { errorToast, successToast } from '@/toasts'
import { useFlowStore } from '@/store/flow'
import { formatUpdatedAgo } from '@/helpers/date'
import { ACCORDION_CONTENT_PT, ACCORDION_HEADER_PT } from '@/prime-vue/pass-through/accordion.pt'
import NotebookLanesCreatePoint from './NotebookLanesCreatePoint.vue'

const toast = useToast()

const flowStore = useFlowStore()

const rewindingStep = ref<number | null>(null)

async function rewind(step: number) {
  rewindingStep.value = step
  try {
    await flowStore.rewindBranch(step)
    toast.add(successToast(`Moved to step ${step}`))
  } catch (error) {
    toast.add(errorToast(error))
  } finally {
    rewindingStep.value = null
  }
}
</script>

<style scoped>
@reference "@/assets/css/index.css";

.header {
  @apply flex items-center gap-1 min-w-0 text-sm font-normal;
}
.head-point {
  @apply max-w-48 truncate text-muted-color;
}
.empty {
  @apply text-sm text-muted-color;
}
.steps {
  @apply flex flex-col max-h-96 overflow-y-auto;
}
.step {
  @apply flex items-center gap-3 py-2 border-b border-surface last:border-b-0;
}
.step-info {
  @apply min-w-0 flex-1;
}
.step-title {
  @apply flex items-center gap-2;
}
.step-intent {
  @apply text-sm truncate;
}
.point-icon {
  @apply shrink-0 text-primary;
}
.step-point-intent {
  @apply text-xs truncate;
}
.step-meta {
  @apply text-xs text-muted-color truncate;
}
</style>
