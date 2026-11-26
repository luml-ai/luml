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
    <div class="panel">
      <div class="ranking">
        <Skeleton width="140px" height="14px" />
        <div class="list">
          <div v-for="index in FEATURES_COUNT" :key="index" class="row">
            <Skeleton width="72px" height="22px" />
            <Skeleton width="100px" height="18px" />
          </div>
        </div>
      </div>
      <div class="details">
        <div class="details-header">
          <Skeleton width="72px" height="22px" />
          <div class="details-actions">
            <Skeleton width="100px" height="18px" />
            <Skeleton width="150px" height="38px" />
          </div>
        </div>
        <div v-for="index in CHARTS_COUNT" :key="index" class="chart">
          <Skeleton width="200px" height="14px" />
          <Skeleton class="chart-skeleton" height="auto" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Card, Divider, Skeleton } from 'primevue'
import { DRIFT_CHART_ASPECT_RATIO } from '@/constants/drift'

const ALERTS_COUNT = 2
const FEATURES_COUNT = 6
const CHARTS_COUNT = 2
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

.panel {
  display: flex;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-card-border-radius);
  background: var(--p-card-background);
  box-shadow: var(--p-card-shadow);
}

.ranking {
  display: flex;
  flex: 0 0 280px;
  flex-direction: column;
  gap: 20px;
  padding: 20px;
  border-right: 1px solid var(--p-divider-border-color);
}

.list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 39px;
  padding: 0 16px;
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
}

.details {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 20px;
  min-width: 0;
  padding: 20px;
}

.details-header,
.details-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.chart {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.chart-skeleton {
  aspect-ratio: v-bind(DRIFT_CHART_ASPECT_RATIO);
}

@media (max-width: 720px) {
  .panel {
    flex-direction: column;
  }

  .ranking {
    flex-basis: auto;
    border-right: none;
    border-bottom: 1px solid var(--p-divider-border-color);
  }
}
</style>
