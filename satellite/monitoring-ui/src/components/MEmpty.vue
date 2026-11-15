<template>
  <Message severity="secondary" class="empty-state">
    <template #icon>
      <Hourglass :size="16" />
    </template>
    <div class="empty-text">
      <span class="empty-title">{{ title }}</span>
      <span v-if="detail" class="empty-detail">{{ detail }}</span>
    </div>
  </Message>
</template>

<script setup lang="ts">
import Message from 'primevue/message'
import { Hourglass } from 'lucide-vue-next'

interface Props {
  title?: string
  detail?: string
}

withDefaults(defineProps<Props>(), {
  title: 'No data',
})
</script>

<style scoped>
.empty-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.empty-title {
  font-size: 14px;
  font-weight: 500;
}

.empty-detail {
  font-size: 12px;
}
</style>
