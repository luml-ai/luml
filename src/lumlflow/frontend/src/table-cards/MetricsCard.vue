<template>
  <div class="mb-5">
    <h3 class="text-lg mb-4">Metrics ({{ metrics.length }})</h3>
    <Card>
      <template #content>
        <IconField class="mb-2">
          <InputText v-model="metricsSearch" placeholder="Search" size="small" fluid />
          <InputIcon>
            <Search :size="12" />
          </InputIcon>
        </IconField>
        <DataTable
          :value="visibleMetrics"
          table-class="table-fixed"
          scrollable
          scrollHeight="200px"
          :virtualScrollerOptions="metrics.length > 10 ? { itemSize: 43 } : undefined"
        >
          <template #empty>
            <div class="flex justify-center items-center h-full">
              <span>No metrics found</span>
            </div>
          </template>
          <Column field="name" header="Metric"></Column>
          <Column field="value" header="Value"></Column>
        </DataTable>
      </template>
    </Card>
  </div>
</template>

<script setup lang="ts">
import { Card, IconField, InputText, InputIcon, DataTable, Column } from 'primevue'
import { computed, ref } from 'vue'
import { Search } from 'lucide-vue-next'

interface Props {
  metrics: { name: string; value: string | number }[]
}

const props = defineProps<Props>()

const metricsSearch = ref('')
const visibleMetrics = computed(() =>
  props.metrics.filter((metric) => metric.name.includes(metricsSearch.value)),
)
</script>

<style scoped></style>
