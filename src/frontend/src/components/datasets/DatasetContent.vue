<template>
  <div>
    <div class="selectors">
      <DatasetDataSelect
        v-if="datasetsStore.selectedSubset"
        :model-value="datasetsStore.selectedSubset.name"
        :heading="subsetsHeading"
        :name="datasetsStore.selectedSubset.name"
        :text="`${getShortcutCountText(datasetsStore.selectedSubset.num_rows)} rows`"
        :options="subsetOptions"
        @update:model-value="datasetsStore.setSelectedSubset($event)"
      />
      <div class="separator"></div>
      <DatasetDataSelect
        v-if="datasetsStore.selectedSplit"
        :model-value="datasetsStore.selectedSplit.name"
        :heading="splitsHeading"
        :name="datasetsStore.selectedSplit.name"
        :text="`${getShortcutCountText(datasetsStore.selectedSplit.num_rows)} rows`"
        :options="splitOptions"
        @update:model-value="datasetsStore.setSelectedSplit($event)"
      />
    </div>

    <DatasetDataTable />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useDatasetsStore } from '@/stores/datasets'
import { getShortcutCountText } from '@/helpers/text'
import DatasetDataSelect from './DatasetDataSelect.vue'
import DatasetDataTable from './DatasetDataTable.vue'

const datasetsStore = useDatasetsStore()

const subsetsHeading = computed(() => {
  return `Subset (${datasetsStore.subsets.length})`
})

const splitsHeading = computed(() => {
  return `Split (${datasetsStore.splitsList.length})`
})

const subsetOptions = computed(() => {
  return datasetsStore.subsets.map((subset) => ({
    label: `${subset.name} (${getShortcutCountText(subset.num_rows)} rows)`,
    value: subset.name,
  }))
})

const splitOptions = computed(() => {
  return datasetsStore.splitsList.map((split) => ({
    label: `${split.name} (${getShortcutCountText(split.num_rows)} rows)`,
    value: split.name,
  }))
})
</script>

<style scoped>
.selectors {
  display: grid;
  grid-template-columns: 1fr 1px 1fr;
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  overflow: hidden;
  background-color: var(--p-content-background);
  box-shadow: var(--card-shadow);
  margin-bottom: 12px;
}

.separator {
  width: 1px;
  height: 100%;
  background-color: var(--p-content-border-color);
}
</style>
