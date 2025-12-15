<template>
  <div>
    <header class="card-header">
      <h3 class="card-title">
        Detailed view
        <triangle-alert
          v-if="isTrainMode"
          :size="20"
          class="warning-icon"
          v-tooltip="
            'Cross-validation was used due to insufficient test data. The sample is from the training set.'
          "
        />
      </h3>
      <div class="detailed-actions">
        <!--<div class="highlight-toggle-wrapper">
          <ToggleSwitch v-model="highlightIncorrect" />
          <span>highlight incorrect</span>
        </div>-->
        <d-button
          variant="text"
          severity="secondary"
          @click="maximizeTable = true"
          :style="{ width: '20px', height: '20px' }"
        >
          <template #icon>
            <Maximize2 :size="20" />
          </template>
        </d-button>
      </div>
    </header>
    <DataTable
      v-if="values.length"
      :value="values"
      showGridlines
      stripedRows
      scrollable
      scrollHeight="19rem"
      :virtualScrollerOptions="{ itemSize: 31 }"
      class="table"
      size="small"
      :style="{ fontSize: '14px' }"
    >
      <Column
        v-for="column in currentColumns"
        :id="column"
        :field="column"
        :header="column === '<=PREDICTED=>' ? 'Prediction' : cutStringOnMiddle(column)"
      >
      </Column>
    </DataTable>
    <Dialog
      v-model:visible="maximizeTable"
      blockScroll
      header="Detailed view"
      class="p-dialog-maximized"
    >
      <template #header>
        <header
          class="card-header"
          :style="{ width: '100%', marginBottom: '0', marginRight: '20px' }"
        >
          <h3 class="card-title">Detailed view</h3>
          <div class="detailed-actions">
            <!--<div class="highlight-toggle-wrapper">
              <ToggleSwitch v-model="highlightIncorrect" />
              <span>highlight incorrect</span>
            </div>-->
          </div>
        </header>
      </template>
      <template #closeicon>
        <Minimize2 />
      </template>
      <DataTable
        v-if="values.length"
        :value="values"
        showGridlines
        stripedRows
        scrollable
        scrollHeight="calc(100vh - 120px)"
        :virtualScrollerOptions="{ itemSize: 31 }"
        class="table"
        size="small"
        :style="{ fontSize: '14px' }"
      >
        <Column
          v-for="column in currentColumns"
          :id="column"
          :field="column"
          :header="column === '<=PREDICTED=>' ? 'Prediction' : cutStringOnMiddle(column)"
        >
        </Column>
      </DataTable>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

import { ToggleSwitch, DataTable, Column, Dialog } from 'primevue'

import { Maximize2, Minimize2, TriangleAlert } from 'lucide-vue-next'

import { cutStringOnMiddle } from '@/helpers/helpers'

type Props = {
  values: object[]
  isTrainMode: boolean
}

const props = defineProps<Props>()

// const highlightIncorrect = ref(false)
const maximizeTable = ref(false)

const currentColumns = computed(() => Object.keys(props.values[0]))
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.card-title {
  font-size: 20px;
}

.detailed-actions {
  display: flex;
  align-items: center;
  gap: 24px;
}

/* .highlight-toggle-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--p-primary-color);
  font-weight: 500;
} */

.table {
  font-size: 14px;
}

.warning-icon {
  color: var(--p-badge-danger-background);
}
</style>
