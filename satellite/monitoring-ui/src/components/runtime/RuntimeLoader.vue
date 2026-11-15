<template>
  <div class="loader">
    <Card class="card">
      <template #content>
        <template v-for="index in ALERTS_COUNT" :key="index">
          <Divider v-if="index > 1" :dt="{ horizontal: { margin: '8px 0' } }" />
          <div class="alert">
            <div class="alert-title">
              <Skeleton shape="circle" size="14px" />
              <Skeleton width="140px" height="14px" />
            </div>
            <Skeleton width="220px" height="12px" />
          </div>
        </template>
      </template>
    </Card>
    <div class="cards">
      <Card v-for="index in CARDS_COUNT" :key="index" class="card">
        <template #title>
          <Skeleton width="60%" height="12px" />
        </template>
        <template #content>
          <Skeleton width="40%" height="28px" />
        </template>
      </Card>
    </div>
    <div class="charts">
      <div v-for="index in CHARTS_COUNT" :key="index" class="chart">
        <div class="chart-header">
          <div class="chart-titles">
            <Skeleton width="140px" height="14px" />
            <Skeleton width="180px" height="12px" />
          </div>
          <Skeleton size="20px" />
        </div>
        <Skeleton :height="`${CHART_HEIGHT}px`" />
      </div>
    </div>
    <Card class="card">
      <template #content>
        <div class="breakdown-header">
          <Skeleton width="160px" height="14px" />
          <Skeleton width="220px" height="12px" />
        </div>
        <div v-for="index in BREAKDOWN_ROWS_COUNT + 1" :key="index" class="breakdown-row">
          <Skeleton width="60%" height="16px" />
          <Skeleton width="40%" height="16px" />
          <Skeleton width="50%" height="16px" />
          <Skeleton width="60px" height="16px" class="breakdown-share" />
        </div>
      </template>
    </Card>
  </div>
</template>

<script setup lang="ts">
import Card from 'primevue/card'
import Divider from 'primevue/divider'
import Skeleton from 'primevue/skeleton'
import { CHART_HEIGHT } from '@/constants/charts'

const ALERTS_COUNT = 2
const CARDS_COUNT = 8
const CHARTS_COUNT = 3
const BREAKDOWN_ROWS_COUNT = 3
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

.card :deep(.p-card-body) {
  gap: 8px;
}

.alert {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  height: 22px;
}

.alert-title {
  display: flex;
  align-items: center;
  gap: 4px;
}

.cards {
  --cards-column-gap: 16px;
  display: grid;
  grid-template-columns: repeat(
    auto-fit,
    minmax(max(260px, (100% - 3 * var(--cards-column-gap)) / 4), 1fr)
  );
  gap: 20px var(--cards-column-gap);
}

.charts {
  --charts-gap: 16px;
  display: grid;
  grid-template-columns: repeat(
    auto-fit,
    minmax(max(260px, (100% - 2 * var(--charts-gap)) / 3), 1fr)
  );
  gap: var(--charts-gap);
}

.chart {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px 20px;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-card-border-radius);
  background: var(--p-card-background);
  box-shadow: var(--p-card-shadow);
}

.chart-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.chart-titles {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.breakdown-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 12px;
}

.breakdown-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr 100px;
  column-gap: 20px;
  align-items: center;
  height: 45px;
  padding: 0 18px 0 10px;
}

.breakdown-row:not(:last-child) {
  border-bottom: 1px solid var(--p-divider-border-color);
}

.breakdown-share {
  justify-self: end;
}
</style>
