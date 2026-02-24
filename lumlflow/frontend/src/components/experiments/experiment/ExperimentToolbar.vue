<template>
  <div class="pb-5 flex justify-between items-center">
    <div class="flex items-center gap-8">
      <div class="tabular-nums">{{ experimentsStore.selectedExperiments.length }} Selected</div>
      <ExperimentButtons />
    </div>
    <div class="flex gap-2 grow justify-end">
      <TableEditColumns
        :columns="experimentsStore.tableColumns"
        :selected-columns="experimentsStore.visibleColumns"
        @edit="(data) => experimentsStore.setVisibleColumns(data)"
      />
      <div class="max-w-sm w-full">
        <IconField>
          <InputText
            v-model="search"
            placeholder="Serch experiment by name or tags"
            size="small"
            fluid
          />
          <InputIcon>
            <Search :size="12" />
          </InputIcon>
        </IconField>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { InputText, IconField, InputIcon } from 'primevue'
import { Search } from 'lucide-vue-next'
import { useExperimentsStore } from '@/store/experiments'
import ExperimentButtons from './ExperimentButtons.vue'
import TableEditColumns from '@/components/table/TableEditColumns.vue'

const experimentsStore = useExperimentsStore()

const search = ref(experimentsStore.queryParams.search || '')

function onSearch() {
  experimentsStore.setQueryParams({ ...experimentsStore.queryParams, search: search.value })
}

watch(search, onSearch)
</script>

<style scoped></style>
