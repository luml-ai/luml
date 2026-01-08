<template>
  <div class="toolbar">
    <h2 class="title">Dynamic Metrics</h2>
    <div class="toolbar-body">
      <Paginator
        :rows="limit"
        :totalRecords="total"
        :alwaysShow="false"
        @page="onPageChange"
      ></Paginator>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { PageState } from 'primevue'
import { Paginator } from 'primevue'

type Props = {
  limit: number
  total: number
}

type Emits = {
  pageChange: [PageState]
}

const props = defineProps<Props>()
const emits = defineEmits<Emits>()

function onPageChange(event: PageState) {
  emits('pageChange', event)
}
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

:deep(.p-iconfield .p-inputtext) {
  width: 100%;
}

.p-iconfield .p-inputtext:not(:last-child) {
  padding-inline-end: calc(var(--p-form-field-padding-x) + var(--p-icon-size));
}

:deep(.p-iconfield .p-inputicon:last-child) {
  inset-inline-end: 9px;
}
</style>
