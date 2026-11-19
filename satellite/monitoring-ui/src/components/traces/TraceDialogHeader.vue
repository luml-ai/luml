<template>
  <div class="header">
    <MEllipsis class="title" :text="title" />
    <div v-if="eventId" class="badge">
      <span class="badge-text">{{ shortEventId }}</span>
      <MCopyButton :text="eventId" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { shortenId } from '@/utils/traces'
import MCopyButton from '@/components/MCopyButton.vue'
import MEllipsis from '@/components/MEllipsis.vue'

interface Props {
  title: string
  eventId: string | null
}

const props = defineProps<Props>()

const shortEventId = computed(() => (props.eventId ? shortenId(props.eventId) : ''))
</script>

<style scoped>
.header {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.title {
  font-size: 16px;
  font-weight: 500;
  color: var(--p-text-color);
}

.badge {
  display: inline-flex;
  flex-shrink: 0;
  align-items: center;
  gap: 4px;
  padding: 2px 4px 2px 8px;
  border-radius: var(--p-tag-border-radius);
  background: var(--p-content-background);
  font-size: 12px;
  color: var(--p-text-color);
}

.badge-text {
  white-space: nowrap;
}
</style>
