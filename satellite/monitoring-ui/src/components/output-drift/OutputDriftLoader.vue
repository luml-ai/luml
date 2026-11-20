<template>
  <div class="loader">
    <Card class="card">
      <template #content>
        <div class="alert">
          <div class="alert-title">
            <Skeleton shape="circle" size="14px" />
            <Skeleton width="140px" height="14px" />
          </div>
          <Skeleton width="220px" height="12px" />
        </div>
      </template>
    </Card>
    <Card class="card metric">
      <template #title>
        <Skeleton width="80px" height="12px" />
      </template>
      <template #content>
        <Skeleton width="100px" height="30px" />
      </template>
      <template #footer>
        <Skeleton width="160px" height="12px" />
      </template>
    </Card>
    <div class="charts">
      <div v-for="index in CHARTS_COUNT" :key="index" class="chart">
        <div class="chart-header">
          <Skeleton width="180px" height="14px" />
          <Skeleton size="20px" />
        </div>
        <Skeleton :height="chartHeight" />
      </div>
    </div>
    <Card v-for="index in LISTS_COUNT" :key="index" class="card">
      <template #content>
        <div class="list-header">
          <Skeleton width="160px" height="14px" />
          <Skeleton width="240px" height="12px" />
        </div>
        <div v-for="row in ROWS_COUNT" :key="row" class="row">
          <Skeleton width="80px" height="16px" />
          <Skeleton width="100px" height="16px" />
          <Skeleton width="60px" height="16px" />
        </div>
      </template>
    </Card>
  </div>
</template>

<script setup lang="ts">
import { Card, Skeleton } from 'primevue'
import { OUTPUT_DRIFT_CHART_HEIGHT } from '@/constants/output-drift'

const CHARTS_COUNT = 2
const LISTS_COUNT = 2
const ROWS_COUNT = 3

const chartHeight = `${OUTPUT_DRIFT_CHART_HEIGHT}px`
</script>

<style scoped>
.loader {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.card {
  border: 1px solid var(--p-content-border-color);
}

.metric {
  align-self: flex-start;
}

.alert,
.alert-title,
.chart-header {
  display: flex;
  align-items: center;
  gap: 4px;
}

.alert,
.chart-header {
  justify-content: space-between;
}

.charts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
}

.chart {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px 20px;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-card-border-radius);
  background: var(--p-card-background);
}

.list-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
}

.row {
  display: grid;
  grid-template-columns: 1fr 2fr 120px;
  gap: 16px;
  padding: 10px;
}

.row > :last-child {
  justify-self: end;
}

@media (max-width: 720px) {
  .charts {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
