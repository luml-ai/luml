<template>
  <div class="header">
    <div class="titles">
      <span class="group">{{ group }}</span>
      <MEllipsis class="title" :text="title" />
    </div>
    <Tag :value="getSeverityLabel(severity)" :severity="getSeverityTagSeverity(severity)" />
  </div>
</template>

<script setup lang="ts">
import { Tag } from 'primevue'
import { getSeverityLabel, getSeverityTagSeverity } from '@/utils/alerts'
import MEllipsis from '@/components/MEllipsis.vue'

interface Props {
  group: string
  title: string
  severity: string
}

defineProps<Props>()
</script>

<style scoped>
.header {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  min-width: 0;
}

.titles {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.group {
  font-size: 12px;
  color: var(--p-text-muted-color);
}

.title {
  font-size: 16px;
  font-weight: 500;
  color: var(--p-text-color);
}
</style>
