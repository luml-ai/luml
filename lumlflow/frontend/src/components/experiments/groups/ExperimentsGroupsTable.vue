<template>
  <DataTable
    :value="groupsStore.groups"
    table-class="min-w-[1100px] table-fixed h-full!"
    scrollable
    scrollHeight="100%"
    :selection="groupsStore.selectedGroups"
    :virtualScrollerOptions="virtualScrollerOptions"
    :pt="tablePt"
    @update:selection="groupsStore.setSelectedGroups"
  >
    <template #empty> <div class="text-center">No experiments groups found</div> </template>
    <Column selectionMode="multiple" class="w-[40px]"></Column>
    <Column field="name" header="Group name" class="w-[180px]"></Column>
    <Column field="created_at" header="Creation time" class="w-[180px]"></Column>
    <Column field="updated_at" header="Last modified" class="w-[180px]"></Column>
    <Column field="description" header="Description" class="w-[302px]">
      <template #body="slotProps">
        <div v-tooltip.top="slotProps.data.description" class="line-clamp-2 h-10.5">
          {{ slotProps.data.description }}
        </div>
      </template>
    </Column>
    <Column field="tags" header="Tags">
      <template #body="slotProps">
        <div class="flex gap-1 flex-nowrap">
          <Tag v-for="tag in slotProps.data.tags" :key="tag">{{ tag }}</Tag>
        </div>
      </template>
    </Column>
  </DataTable>
</template>

<script setup lang="ts">
import type { DataTablePassThroughOptions, VirtualScrollerProps } from 'primevue'
import { DataTable, Column, Tag } from 'primevue'
import { useGroupsStore } from '@/store/groups'

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
</script>

<style scoped></style>
