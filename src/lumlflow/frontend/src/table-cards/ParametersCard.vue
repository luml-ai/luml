<template>
  <div class="mb-5">
    <h3 class="text-lg mb-4">Parameters ({{ parameters.length }})</h3>
    <Card>
      <template #content>
        <IconField class="mb-2">
          <InputText v-model="parametersSearch" placeholder="Search" size="small" fluid />
          <InputIcon>
            <Search :size="12" />
          </InputIcon>
        </IconField>
        <DataTable
          :value="visibleParameters"
          table-class="table-fixed"
          scrollable
          scrollHeight="200px"
          :virtualScrollerOptions="parameters.length > 10 ? { itemSize: 43 } : undefined"
        >
          <template #empty>
            <div class="flex justify-center items-center h-full">
              <span>No parameters found</span>
            </div>
          </template>
          <Column field="name" header="Parameter"></Column>
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
  parameters: { name: string; value: string | number }[]
}

const props = defineProps<Props>()

const parametersSearch = ref('')
const visibleParameters = computed(() =>
  props.parameters.filter((parameter) => parameter.name.includes(parametersSearch.value)),
)
</script>

<style scoped></style>
