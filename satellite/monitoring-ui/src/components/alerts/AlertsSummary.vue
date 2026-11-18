<template>
  <div class="summary">
    <span>{{ openCount }} open</span>
    <span v-if="criticalCount" class="summary-critical">{{ criticalCount }} critical</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Severity, type AlertGroup } from '@/api/monitoring/interfaces'
import { countAlerts } from '@/utils/alerts'

interface Props {
  groups: AlertGroup[]
}

const props = defineProps<Props>()

const openCount = computed(() => countAlerts(props.groups))

const criticalCount = computed(() => countAlerts(props.groups, Severity.CRITICAL))
</script>

<style scoped>
.summary {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  padding: 0 4px;
  font-size: 14px;
  font-weight: 500;
}

.summary-critical {
  color: var(--p-message-error-color);
}
</style>
