<template>
  <div>
    <Button variant="text" class="px-2.5! w-full" @click="toggle">
      <Flag v-if="currentPointName" :size="14" />
      <History v-else :size="14" />
      <span>Step {{ flowStore.currentHeadStep }}</span>
      <span v-if="currentPointName" class="head-point">· {{ currentPointName }}</span>
    </Button>
    <Popover ref="popoverRef" :pt="POPOVER_WITHOUT_ARROW_PT" class="w-96">
      <p v-if="!flowStore.currentBranchSteps.length" class="empty">Nothing on this lane yet</p>
      <ol v-else class="steps">
        <li v-for="step in flowStore.currentBranchSteps" :key="step.step" class="step">
          <Flag v-if="flowStore.currentBranchPoints.has(step.step)" :size="14" class="point-icon" />
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
    </Popover>
  </div>
</template>

<script setup lang="ts">
import { Button, Popover, Tag } from 'primevue'
import { Flag, History } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import { errorToast, successToast } from '@/toasts'
import { useFlowStore } from '@/store/flow'
import { formatUpdatedAgo } from '@/helpers/date'
import { POPOVER_WITHOUT_ARROW_PT } from '@/prime-vue/pass-through/popover.pt'

const toast = useToast()

const flowStore = useFlowStore()

const popoverRef = ref<InstanceType<typeof Popover>>()

const rewindingStep = ref<number | null>(null)

const currentPointName = computed(() => {
  const step = flowStore.currentHeadStep
  return step === null ? undefined : flowStore.currentBranchPoints.get(step)
})

function toggle(event: Event) {
  popoverRef.value?.toggle(event)
}

async function rewind(step: number) {
  rewindingStep.value = step
  try {
    await flowStore.rewindBranch(step)
    popoverRef.value?.hide()
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

.head-point {
  @apply max-w-48 truncate;
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
