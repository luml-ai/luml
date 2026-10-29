<template>
  <Message
    v-if="flowStore.isBehindLaneHead && newestStep !== null"
    severity="warn"
    size="small"
  >
    <div class="behind-message">
      <span>
        The lane is on step {{ flowStore.currentHeadStep }}, not its latest step
        {{ newestStep }}.
      </span>
      <Button
        label="Back to latest"
        size="small"
        variant="text"
        :loading="rewindingStep === newestStep"
        :disabled="rewindingStep !== null"
        @click="emit('back', newestStep)"
      />
    </div>
  </Message>
</template>

<script setup lang="ts">
import { Button, Message } from 'primevue'
import { computed } from 'vue'
import { useFlowStore } from '@/store/flow'

defineProps<{ rewindingStep: number | null }>()

const emit = defineEmits<{
  back: [step: number]
}>()

const flowStore = useFlowStore()

const newestStep = computed(() => flowStore.currentBranch?.newest_step ?? null)
</script>

<style scoped>
@reference "@/assets/css/index.css";

.behind-message {
  @apply flex items-center justify-between gap-2;
}
</style>
