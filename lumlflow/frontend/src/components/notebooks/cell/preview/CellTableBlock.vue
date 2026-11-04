<template>
  <div class="flex flex-col gap-2">
    <DataTable :value="rows" scrollable scrollHeight="240px" size="small">
      <Column
        v-for="column in block.columns"
        :key="column"
        :field="column"
        :header="column"
      ></Column>
    </DataTable>
    <div class="table-footer">
      <p class="text-sm text-muted-color">{{ shownRows }} of {{ block.total_rows }} rows</p>
      <Button
        v-if="canLoadMore"
        label="Show more rows"
        size="small"
        variant="text"
        :loading="isLoadingMore"
        @click="loadMore"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { CellTableBlockProps } from './preview.interface'
import { Button, Column, DataTable } from 'primevue'
import { computed, ref, watch } from 'vue'
import { useToast } from 'primevue/usetoast'
import { errorToast } from '@/toasts'
import { useFlowStore } from '@/store/flow'

// The preview carries the first rows only; the rest come from `asset.page`.
const PAGE_ROWS = 100

const props = defineProps<CellTableBlockProps>()

const flowStore = useFlowStore()
const toast = useToast()

const extraRows = ref<CellTableBlockProps['block']['rows']>([])
const isLoadingMore = ref(false)

watch(
  () => props.block,
  () => {
    extraRows.value = []
  },
)

const allRows = computed(() => [...props.block.rows, ...extraRows.value])
const shownRows = computed(() => allRows.value.length)
const canLoadMore = computed(
  () => !!props.slug && !!props.output && shownRows.value < props.block.total_rows,
)

const rows = computed(() =>
  allRows.value.map((row) =>
    Object.fromEntries(props.block.columns.map((column, index) => [column, row[index]])),
  ),
)

async function loadMore() {
  if (!props.slug || !props.output || isLoadingMore.value) return
  isLoadingMore.value = true
  try {
    const { page } = await flowStore.fetchAssetPage(
      props.slug,
      props.output,
      shownRows.value,
      PAGE_ROWS,
    )
    // Columns are matched by name: a page may order them differently.
    const order = props.block.columns.map((column) => page.columns.indexOf(column))
    extraRows.value = [
      ...extraRows.value,
      ...page.rows.map((row) => order.map((index) => (index >= 0 ? (row[index] ?? null) : null))),
    ]
  } catch (error) {
    toast.add(errorToast(error, 'Failed to load more rows'))
  } finally {
    isLoadingMore.value = false
  }
}
</script>

<style scoped>
@reference "@/assets/css/index.css";

.table-footer {
  @apply flex items-center justify-between gap-2;
}
</style>
