<template>
  <div class="loader">
    <div class="cards">
      <Card v-for="index in CARDS_COUNT" :key="index" class="card">
        <template #title>
          <Skeleton width="60%" height="12px" />
        </template>
        <template #content>
          <Skeleton width="40%" height="28px" />
        </template>
        <template #footer>
          <Skeleton width="70%" height="12px" />
        </template>
      </Card>
    </div>
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
        <div class="features-header">
          <Skeleton width="160px" height="14px" />
          <Skeleton width="200px" height="12px" />
        </div>
        <div class="features">
          <div v-for="index in FEATURES_COUNT" :key="index" class="feature">
            <div class="feature-head">
              <Skeleton width="80px" height="14px" />
              <Skeleton width="70px" height="14px" />
            </div>
            <Skeleton height="6px" border-radius="6px" />
          </div>
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

const CARDS_COUNT = 6
const ALERTS_COUNT = 3
const FEATURES_COUNT = 3
const CHARTS_COUNT = 3
</script>

<style scoped>
.loader {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.cards {
  --cards-gap: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: var(--cards-gap);
}

.cards > * {
  flex: 1 1 max(130px, (100% - 5 * var(--cards-gap)) / 6);
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

.features-header {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 24px;
}

.features {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.feature {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.feature-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
</style>
