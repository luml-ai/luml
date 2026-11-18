<template>
  <MTableCard>
    <div class="summary">
      <Skeleton width="60px" height="14px" />
      <Skeleton width="70px" height="14px" />
    </div>
    <div class="table">
      <div class="row head">
        <Skeleton v-for="index in columnsCount" :key="index" width="60%" height="14px" />
      </div>
      <template v-for="group in GROUPS_COUNT" :key="group">
        <div class="group" :class="{ divided: group > 1 }">
          <Skeleton width="120px" height="14px" />
        </div>
        <div v-for="index in ROWS_PER_GROUP" :key="index" class="row">
          <div class="name">
            <Skeleton shape="circle" size="8px" />
            <Skeleton width="70%" height="14px" />
          </div>
          <Skeleton width="70%" height="14px" />
          <Skeleton width="50%" height="14px" />
          <Skeleton width="60px" height="18px" />
          <Skeleton width="40px" height="14px" class="numeric" />
        </div>
      </template>
    </div>
  </MTableCard>
</template>

<script setup lang="ts">
import { Skeleton } from 'primevue'
import MTableCard from '@/components/MTableCard.vue'
import { ALERTS_COLUMN_WIDTHS } from '@/constants/alerts'

const GROUPS_COUNT = 3
const ROWS_PER_GROUP = 2

const columnsCount = Object.keys(ALERTS_COLUMN_WIDTHS).length

const gridColumns = Object.values(ALERTS_COLUMN_WIDTHS)
  .map((width) => `${width}fr`)
  .join(' ')
</script>

<style scoped>
.summary {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  padding: 0 4px;
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
}

.row.head {
  border-bottom: 1px solid var(--p-datatable-body-cell-border-color);
  background: var(--p-datatable-header-cell-background);
}

.group {
  display: flex;
  align-items: center;
  height: 44px;
  padding: 0 16px;
}

.group.divided {
  border-top: 1px solid var(--p-datatable-body-cell-border-color);
}

.name {
  display: flex;
  align-items: center;
  gap: 8px;
}

.numeric {
  justify-self: end;
}
</style>
