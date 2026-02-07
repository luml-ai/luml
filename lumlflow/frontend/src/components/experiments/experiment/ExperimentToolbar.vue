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
        <InputGroup>
          <InputText v-model="search" placeholder="Serch experiment by name or tags" size="small" />
          <InputGroupAddon>
            <Button severity="secondary" class="h-full" size="small" fluid @click="onSearch">
              <template #icon>
                <Search :size="12" />
              </template>
            </Button>
          </InputGroupAddon>
        </InputGroup>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { InputGroup, InputGroupAddon, InputText, Button } from 'primevue'
import { Search } from 'lucide-vue-next'
import { useExperimentsStore } from '@/store/experiments'
import ExperimentButtons from './ExperimentButtons.vue'
import TableEditColumns from '@/components/table/TableEditColumns.vue'

const experimentsStore = useExperimentsStore()

const search = ref('')

function onSearch() {
  console.log(search.value)
}
</script>

<style scoped></style>
