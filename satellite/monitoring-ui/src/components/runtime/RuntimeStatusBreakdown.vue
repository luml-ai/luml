<template>
  <Card class="breakdown">
    <template #content>
      <div class="header">
        <h3 class="title">Outcome breakdown</h3>
        <span class="subtitle">How the calls in this window ended</span>
      </div>
      <table v-if="rows.length" class="table">
        <colgroup>
          <col />
          <col />
          <col />
          <col class="share-column" />
        </colgroup>
        <thead>
          <tr>
            <th>Outcome</th>
            <th>Code</th>
            <th>Calls</th>
            <th class="share">Share</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="getStatusRowKey(row)">
            <td :class="{ failed: isFailedOutcome(row) }">{{ getOutcomeLabel(row.status) }}</td>
            <td>{{ row.status_code ?? '—' }}</td>
            <td>{{ formatInteger(row.count) }}</td>
            <td class="share">{{ formatPercent(row.share) }}</td>
          </tr>
        </tbody>
      </table>
      <span v-else class="empty">No calls to break down.</span>
    </template>
  </Card>
</template>

<script setup lang="ts">
import Card from 'primevue/card'
import type { StatusBreakdownRow } from '@/api/monitoring/interfaces'
import { formatInteger, formatPercent } from '@/utils/format'
import { getOutcomeLabel, getStatusRowKey, isFailedOutcome } from '@/utils/runtime'

interface Props {
  rows: StatusBreakdownRow[]
}

withDefaults(defineProps<Props>(), {
  rows: () => [],
})
</script>

<style scoped>
.breakdown {
  border: 1px solid var(--p-content-border-color);
}

.header {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
}

.title {
  font-size: 14px;
  font-weight: 500;
  color: var(--p-text-color);
}

.subtitle,
.empty {
  font-size: 12px;
  color: var(--p-text-muted-color);
}

.table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 16px;
  color: var(--p-text-color);
}

.share-column {
  width: 120px;
}

th,
td {
  overflow: hidden;
  padding: 10px;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
}

th {
  font-weight: 500;
}

td {
  font-weight: 400;
}

thead tr,
tbody tr:not(:last-child) {
  border-bottom: 1px solid var(--p-divider-border-color);
}

.share {
  padding-right: 18px;
  text-align: right;
}

.failed {
  color: var(--p-message-error-color);
}
</style>
