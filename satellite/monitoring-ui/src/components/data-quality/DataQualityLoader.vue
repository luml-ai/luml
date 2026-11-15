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
    <MTableCard>
      <div class="table">
        <div
          v-for="index in ROWS_COUNT + 1"
          :key="index"
          class="row"
          :class="{ head: index === 1 }"
        >
          <Skeleton width="60%" height="14px" />
          <Skeleton width="50%" height="14px" />
          <Skeleton width="50%" height="14px" />
          <Skeleton width="70%" height="14px" />
          <Skeleton width="60px" height="18px" />
        </div>
      </div>
    </MTableCard>
  </div>
</template>

<script setup lang="ts">
import { Card, Divider, Skeleton } from 'primevue'
import MTableCard from '@/components/MTableCard.vue'
import { DATA_QUALITY_COLUMN_WIDTHS } from '@/constants/data-quality'

const ALERTS_COUNT = 2
const ROWS_COUNT = 6

const gridColumns = Object.values(DATA_QUALITY_COLUMN_WIDTHS)
  .map((width) => `${width}fr`)
  .join(' ')
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

.table {
  overflow: hidden;
}

.row {
  display: grid;
  grid-template-columns: v-bind(gridColumns);
  align-items: center;
  height: 44px;
  padding: 0 16px;
  column-gap: 32px;
  border-bottom: 1px solid var(--p-datatable-body-cell-border-color);
}

.row.head {
  background: var(--p-datatable-header-cell-background);
}
</style>
