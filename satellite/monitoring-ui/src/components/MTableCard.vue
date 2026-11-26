<template>
  <div class="table-card">
    <slot />
  </div>
</template>

<style scoped>
.table-card {
  --p-datatable-row-background: transparent;
  --p-datatable-row-striped-background: transparent;
  --p-paginator-background: transparent;
  --p-datatable-paginator-top-border-width: 0;
  --p-datatable-paginator-bottom-border-width: 0;
  padding: 12px 12px 16px;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-card-border-radius);
  background: var(--p-card-background);
}

.table-card :deep(.numeric) {
  text-align: right;
}

.table-card :deep(.numeric .p-datatable-column-header-content) {
  justify-content: flex-end;
}
</style>
