<template>
  <FlowCard
    :name="flow.name"
    kind="local"
    :status-class="status.className"
    :status-tooltip="status.tooltip"
  >
    <template #actions>
      <a
        :href="localFlowUrl(flow)"
        target="_blank"
        rel="noopener noreferrer"
        class="open-link"
        v-tooltip.top="'Open in a new tab'"
        data-testid="open-flow"
      >
        <ExternalLink :size="14" />
      </a>
      <Button
        variant="text"
        severity="secondary"
        v-tooltip.top="'Remove'"
        data-testid="remove-flow"
        @click="$emit('remove')"
      >
        <template #icon><Trash2 :size="14" /></template>
      </Button>
    </template>
    <span data-testid="flow-address">{{ localFlowKey(flow) }}</span>
    <span>{{ status.text }}</span>
  </FlowCard>
</template>

<script setup lang="ts">
import type { LocalFlow } from '@/utils/services/LocalStorageService.interfaces'
import { computed } from 'vue'
import { Button } from 'primevue'
import { ExternalLink, Trash2 } from 'lucide-vue-next'
import { localFlowKey, localFlowUrl } from '@/stores/local-flows'
import FlowCard from './FlowCard.vue'

type Props = {
  flow: LocalFlow
  reachable: boolean | null
}

type Emits = {
  remove: []
}

const props = defineProps<Props>()
defineEmits<Emits>()

const status = computed(() => {
  if (props.reachable === null) {
    return { className: '', tooltip: 'Checking', text: 'Checking whether lumlflow answers' }
  }
  if (props.reachable) {
    return { className: 'status--success', tooltip: 'Answering', text: 'lumlflow answers' }
  }
  return {
    className: 'status--danger',
    tooltip: 'Not answering right now',
    text: 'Not answering right now',
  }
})
</script>

<style scoped>
.open-link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 6px;
  color: var(--p-text-muted-color);
}

.open-link:hover {
  background-color: var(--p-content-hover-background);
}
</style>
