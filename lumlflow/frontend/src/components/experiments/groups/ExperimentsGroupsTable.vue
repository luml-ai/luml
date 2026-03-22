<template>
  <DataTable
    :value="groupsStore.data"
    table-class="min-w-[1100px] table-fixed"
    scrollable
    scrollHeight="100%"
    :selection="groupsStore.selectedGroups"
    :virtualScrollerOptions="virtualScrollerOptions"
    :pt="{
      tableContainer: {
        class: 'h-full',
      },
      emptyMessage: loading ? 'hidden' : '',
    }"
    :loading="loading"
    @update:selection="groupsStore.setSelectedGroups"
    @row-click="onRowClick"
    @sort="onSort"
  >
    <template #empty>
      <div class="text-center min-h-full">No experiment groups found.</div>
    </template>
    <Column selectionMode="multiple" class="w-[40px]"></Column>
    <Column field="name" header="Group name" sortable class="w-[180px]">
      <template #body="slotProps">
        <div v-tooltip.top="slotProps.data.name.length > 14 ? slotProps.data.name : null">
          {{ cutStringOnMiddle(slotProps.data.name, 14) }}
        </div>
      </template>
    </Column>
    <Column field="created_at" header="Creation time" sortable class="w-[180px]">
      <template #body="slotProps">
        <span>{{ dateToText(slotProps.data.created_at) }}</span>
      </template>
    </Column>
    <Column field="last_modified" header="Last modified" sortable class="w-[180px]">
      <template #body="slotProps">
        <span>{{ dateToText(slotProps.data.last_modified) }}</span>
      </template>
    </Column>
    <Column field="description" header="Description" sortable>
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
import type { DataTableRowClickEvent, DataTableSortEvent, VirtualScrollerProps } from 'primevue'
import type { GetGroupsParams } from '@/api/api.interface'
import { DataTable, Column, useToast } from 'primevue'
import { useGroupsStore } from '@/store/groups'
import { ROUTE_NAMES } from '@/router/router.const'
import { useRouter } from 'vue-router'
import { onBeforeMount, onBeforeUnmount, ref } from 'vue'
import { dateToText } from '@/helpers/date'
import { errorToast } from '@/toasts'
import { cutStringOnMiddle } from '@/helpers/string'
import ColumnTags from '@/components/table/ColumnTags.vue'
import ColumnDescription from '@/components/table/ColumnDescription.vue'

const toast = useToast()

const router = useRouter()

const groupsStore = useGroupsStore()

const loading = ref(true)

const virtualScrollerOptions: VirtualScrollerProps = {
  lazy: true,
  itemSize: 64,
  scrollHeight: '100%',
  onLazyLoad: groupsStore.onLazyLoad,
}

function onRowClick(event: DataTableRowClickEvent) {
  const target = event.originalEvent.target as HTMLElement
  const rowIncludeCheckbox = !!target.querySelector('input[type="checkbox"]')
  if (rowIncludeCheckbox) return
  const id = event.data.id
  if (!id) return
  router.push({ name: ROUTE_NAMES.EXPERIMENT, params: { groupId: String(id) } })
}

async function onSort(event: DataTableSortEvent) {
  const { sortField, sortOrder } = event
  groupsStore.setQueryParams({
    ...groupsStore.queryParams,
    sort_by: sortField as GetGroupsParams['sort_by'],
    order: sortOrder === 1 ? 'asc' : 'desc',
  })
}

onBeforeMount(async () => {
  try {
    await groupsStore.getInitialPage()
  } catch (error) {
    toast.add(errorToast(error))
  } finally {
    loading.value = false
  }
})

onBeforeUnmount(() => {
  groupsStore.reset()
})
</script>

<style scoped></style>
