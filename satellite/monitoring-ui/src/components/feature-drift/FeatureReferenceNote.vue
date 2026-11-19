<template>
  <Message :severity="severity">
    <template #icon>
      <Info :size="16" />
    </template>
    <div class="text">
      <span class="title">{{ title }}</span>
      <span class="detail">{{ detail }}</span>
    </div>
  </Message>
</template>

<script setup lang="ts">
import { Info } from 'lucide-vue-next'
import { Message } from 'primevue'
import type { ReferenceNote } from '@/types/reference-profile'

defineProps<ReferenceNote>()
</script>

<style scoped>
.text {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.title {
  font-size: 14px;
  font-weight: 500;
}

.detail {
  font-size: 12.25px;
  font-weight: 500;
  color: var(--p-text-color);
}
</style>
