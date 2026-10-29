<template>
  <Accordion class="accordion border-t border-surface">
    <AccordionPanel value="1" class="border-none!">
      <AccordionHeader class="bg-transparent!" :pt="ACCORDION_HEADER_PT">
        <div class="header">
          <History :size="14" color="var(--p-text-muted-color)" />
          <span class="text-color">Steps</span>
          <span class="text-muted-color">({{ flowStore.currentBranchSteps.length }})</span>
          <span v-if="flowStore.isBehindLaneHead" class="behind-badge">
            on step {{ flowStore.currentHeadStep }}
          </span>
        </div>
      </AccordionHeader>
      <AccordionContent :pt="ACCORDION_CONTENT_PT">
        <NotebookLanesBehindMessage
          class="mb-2"
          :rewinding-step="rewindingStep"
          @back="rewind"
        />
        <p v-if="!flowStore.currentBranchSteps.length" class="empty">Nothing on this lane yet</p>
        <ol v-else class="steps">
          <li
            v-for="step in flowStore.currentBranchSteps"
            :key="step.step"
            class="step"
            :class="{
              'step--current': step.step === flowStore.currentHeadStep,
              'step--busy': rewindingStep === step.step,
            }"
            :aria-current="step.step === flowStore.currentHeadStep ? 'step' : undefined"
            :tabindex="step.step === flowStore.currentHeadStep ? -1 : 0"
            :data-step="step.step"
            @click="confirmRewind(step.step)"
            @keydown.enter.self="confirmRewind(step.step)"
          >
            <Flag
              v-if="flowStore.currentBranchPoints.has(step.step)"
              :size="16"
              class="point-icon"
            />
            <div class="step-info">
              <div class="step-intent" v-overflow-tooltip.top="stepTitle(step)">
                {{ stepTitle(step) }}
              </div>
              <div
                v-if="flowStore.currentBranchPoints.has(step.step)"
                class="step-point-intent"
                v-overflow-tooltip.top="step.intent"
              >
                {{ step.intent }}
              </div>
              <div class="step-meta">
                step {{ step.step }} · {{ formatUpdatedAgo(step.ts) }} · {{ step.actor }}
              </div>
            </div>
            <NotebookLanesCreatePoint
              v-if="!flowStore.currentBranchPoints.has(step.step)"
              :step="step.step"
              class="step-point"
            />
          </li>
        </ol>
      </AccordionContent>
    </AccordionPanel>
  </Accordion>
</template>

<script setup lang="ts">
import type { JournalTransaction } from '@/api/slices/workspace/workspace.interface'
import {
  Accordion,
  AccordionContent,
  AccordionHeader,
  AccordionPanel,
  useConfirm,
} from 'primevue'
import { Flag, History } from 'lucide-vue-next'
import { ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import { errorToast, successToast } from '@/toasts'
import { useFlowStore } from '@/store/flow'
import { moveLaneConfirmOptions } from '@/confirm/confirm'
import { useDiscardConfirm } from '@/composables/useDiscardConfirm'
import { formatUpdatedAgo } from '@/helpers/date'
import { ACCORDION_CONTENT_PT, ACCORDION_HEADER_PT } from '@/prime-vue/pass-through/accordion.pt'
import NotebookLanesCreatePoint from './NotebookLanesCreatePoint.vue'
import NotebookLanesBehindMessage from './NotebookLanesBehindMessage.vue'

const toast = useToast()
const confirm = useConfirm()
const { confirmLeave } = useDiscardConfirm()

const flowStore = useFlowStore()

const rewindingStep = ref<number | null>(null)

function stepTitle(step: JournalTransaction): string {
  return flowStore.currentBranchPoints.get(step.step) ?? step.intent
}

async function confirmRewind(step: number) {
  const lane = flowStore.currentBranch?.branch
  if (!lane || step === flowStore.currentHeadStep || rewindingStep.value !== null) return
  if (!(await confirmLeave())) return
  const isLatest = step === flowStore.currentBranch?.newest_step
  confirm.require(
    moveLaneConfirmOptions(() => {
      if (flowStore.currentBranch?.branch !== lane) {
        toast.add(errorToast(new Error(`Lane ${lane} is no longer checked out, nothing was moved`)))
        return
      }
      rewind(step)
    }, { lane, step, isLatest }),
  )
}

async function rewind(step: number) {
  if (step === flowStore.currentHeadStep || rewindingStep.value !== null) return
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
.behind-badge {
  @apply ml-1 text-xs text-(--p-message-warn-color) truncate;
}
.accordion :deep(.p-collapsible-leave-active) {
  @apply pointer-events-none;
}
.head-point {
  @apply max-w-48 truncate text-muted-color;
}
.empty {
  @apply text-sm text-muted-color;
}
.steps {
  @apply flex flex-col gap-1 max-h-96 overflow-y-auto;
}
.step {
  @apply flex items-center gap-3 px-3 py-2 rounded-md cursor-pointer transition-colors;
}
.step:hover {
  @apply bg-(--p-content-hover-background);
}
.step--current,
.step--current:hover {
  @apply bg-(--p-highlight-background) cursor-default;
}
.step--busy {
  @apply opacity-60 pointer-events-none;
}
.step-info {
  @apply min-w-0 flex-1;
}
.step-intent {
  @apply text-sm truncate text-color;
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
.step-point {
  @apply shrink-0 invisible;
}
.step:hover .step-point,
.step:focus-within .step-point,
.step--current .step-point {
  @apply visible;
}
</style>
