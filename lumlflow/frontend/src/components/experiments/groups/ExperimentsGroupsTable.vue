<template>
  <DataTable
    :value="groupsStore.groups"
    table-class="min-w-[1100px] table-fixed"
    scrollable
    scrollHeight="100%"
    :selection="groupsStore.selectedGroups"
    :virtualScrollerOptions="virtualScrollerOptions"
    :pt="tablePt"
    @update:selection="groupsStore.setSelectedGroups"
    @row-click="onRowClick"
  >
    <template #empty> <div class="text-center">No experiments groups found</div> </template>
    <Column selectionMode="multiple" class="w-[40px]"></Column>
    <Column field="name" header="Group name" class="w-[180px]"></Column>
    <Column field="created_at" header="Creation time" class="w-[180px]"></Column>
    <Column field="updated_at" header="Last modified" class="w-[180px]"></Column>
    <Column field="description" header="Description">
      <template #body="slotProps">
        <ColumnDescription :description="slotProps.data.description" />
      </template>
    </Column>
    <Column field="tags" header="Tags" class="w-[280px]">
      <template #body="slotProps">
        <ColumnTags :tags="slotProps.data.tags || []" :width="220" />
      </template>
    </Column>
  </DataTable>
</template>

<script setup lang="ts">
import type {
  DataTablePassThroughOptions,
  DataTableRowClickEvent,
  VirtualScrollerProps,
} from 'primevue'
import { DataTable, Column } from 'primevue'
import { useGroupsStore } from '@/store/groups'
import { ROUTE_NAMES } from '@/router/router.const'
import { useRouter } from 'vue-router'
import ColumnTags from '@/components/table/ColumnTags.vue'
import ColumnDescription from '@/components/table/ColumnDescription.vue'

const router = useRouter()

const tablePt: DataTablePassThroughOptions = {
  tableContainer: {
    class: 'h-full',
  },
}

const virtualScrollerOptions: VirtualScrollerProps = {
  lazy: true,
  itemSize: 58.75,
  scrollHeight: '100%',
}

const groupsStore = useGroupsStore()

function onRowClick(event: DataTableRowClickEvent) {
  const target = event.originalEvent.target as HTMLElement
  const rowIncludeCheckbox = !!target.querySelector('input[type="checkbox"]')
  if (rowIncludeCheckbox) return
  const id = event.data.id
  if (!id) return
  router.push({ name: ROUTE_NAMES.EXPERIMENT, params: { experimentId: String(id) } })
}
</script>

<style scoped></style>
