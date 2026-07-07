<template>
  <section class="data-quality" data-testid="data-quality-tab">
    <div class="intro">
      <p class="section-title">Data quality</p>
      <p class="section-subtitle">
        Are incoming features well-formed, or did an upstream pipeline break?
      </p>
    </div>

    <div class="card">
      <StateBlock
        v-if="view !== 'ready'"
        :view="view"
        :skeleton-rows="4"
        empty-title="No data quality results yet"
        empty-detail="The worker has not materialized data quality for this window yet."
      />

      <div v-else-if="dataQuality" class="table-scroll">
        <table class="dq" data-testid="data-quality-table">
          <thead>
            <tr>
              <th>Feature</th>
              <th class="num">Missing</th>
              <th class="num">Type errors</th>
              <th class="num">Range / unseen</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in dataQuality.features" :key="row.feature" data-testid="dq-row">
              <td class="mono feature">{{ row.feature }}</td>
              <td class="num">{{ formatRate(row.missing_rate) }}</td>
              <td class="num">{{ formatRate(row.type_error_rate) }}</td>
              <td class="num">{{ formatRate(row.range_unseen_rate) }}</td>
              <td><SeverityTag :severity="row.status" /></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <AlertBannerList v-if="dataQuality?.alerts?.length" :banners="dataQuality.alerts" />

    <TracesPanel :traces="traces" :status="tracesStatus" @page="$emit('traces-page', $event)" />
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { DataQualityResponse, TracesResponse } from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'
import { sectionView } from '@/lib/section'
import { formatRate } from '@/lib/format'
import StateBlock from '@/components/StateBlock.vue'
import SeverityTag from '@/components/SeverityTag.vue'
import TracesPanel from '@/components/TracesPanel.vue'
import AlertBannerList from '@/components/overview/AlertBannerList.vue'

const props = defineProps<{
  dataQuality: DataQualityResponse | null
  status: LoadStatus
  traces: TracesResponse | null
  tracesStatus: LoadStatus
}>()

defineEmits<{ 'traces-page': [number] }>()

const view = computed(() => sectionView(props.status, props.dataQuality?.state))
</script>

<style scoped>
.data-quality {
  display: flex;
  flex-direction: column;
  gap: var(--luml-space-4);
}
.table-scroll {
  overflow-x: auto;
}
.dq {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.dq th {
  text-align: left;
  padding: 8px 12px;
  color: var(--luml-fg-muted);
  font-weight: 500;
  border-bottom: 1px solid var(--luml-border);
  white-space: nowrap;
}
.dq td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--luml-surface-100);
  color: var(--luml-fg);
}
.dq .num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.feature {
  font-weight: 500;
  color: var(--luml-fg-strong);
}
</style>
