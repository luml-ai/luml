<template>
  <Stepper
    :value="currentStep"
    class="stepper"
    @update:value="(step: number) => (currentStep = step)"
  >
    <StepList>
      <Step
        v-for="step in steps"
        :key="step.id"
        :value="step.id"
        :disabled="!isStepAvailable(step.id)"
      >
        <span class="step-label">
          {{ step.text }}
        </span>
      </Step>
    </StepList>
    <StepPanels class="steppanels">
      <StepPanel v-slot="{ activateCallback }" :value="1">
        <upload-data
          v-if="currentStep === 1"
          :errors="uploadDataErrors"
          :is-table-exist="isTableExist"
          :file="fileData"
          :min-columns-count="3"
          :min-rows-count="100"
          :resources="resources"
          :sample-file-name="sampleFileName"
          @selectFile="onSelectFile"
          @removeFile="onRemoveFile"
        />
        <div class="navigation">
          <d-button label="Back" severity="secondary" @click="$router.push({ name: 'home' })" />
          <d-button :disabled="!isStepAvailable(2)" @click="activateCallback(2)">
            <span style="font-weight: 500">Continue</span>
            <arrow-right width="14" height="14" />
          </d-button>
        </div>
      </StepPanel>
      <StepPanel v-slot="{ activateCallback }" :value="2">
        <table-view
          v-if="currentStep === 2 && columnsCount && rowsCount && viewValues"
          :columns-count="columnsCount"
          :rows-count="rowsCount"
          :all-columns="getAllColumnNames"
          :value="viewValues"
          :target="getTarget"
          :group="getGroup"
          :selected-columns="selectedColumns"
          :export-callback="downloadCSV"
          :filters="getFilters"
          :columnTypes="columnTypes"
          show-column-header-menu
          @set-target="setTarget"
          @change-group="changeGroup"
          @edit="setSelectedColumns"
          @change-filters="setFilters"
        />
        <div class="navigation">
          <d-button label="Back" severity="secondary" @click="activateCallback(1)" />
          <d-button @click="startTraining">
            <span style="font-weight: 500">Continue</span>
            <arrow-right width="14" height="14" />
          </d-button>
        </div>
      </StepPanel>
      <StepPanel :value="3">
        <service-evaluate
          v-if="currentStep === 3 && trainingModelId"
          :prediction-fields="getPredictionFields"
          :total-score="getTotalScore"
          :test-metrics="getTestMetrics"
          :training-metrics="getTrainingMetrics"
          :features="getTop5Feature"
          :predicted-data="getPredictedData as Record<string, []>"
          :is-train-mode="isTrainMode"
          :download-model-callback="downloadModel"
          :training-model-id="trainingModelId"
          :current-task="currentTask"
          :model-blob="modelBlob"
        />
      </StepPanel>
    </StepPanels>
  </Stepper>
  <ui-training v-model="isLoading" :time="8" />
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Tasks } from '@/lib/data-processing/interfaces'
import { useDataTable } from '@/hooks/useDataTable'
import { useModelTraining } from '@/hooks/useModelTraining'
import { classificationResources, regressionResources } from '@/constants/constants'
import { ArrowRight } from 'lucide-vue-next'
import Stepper from 'primevue/stepper'
import StepList from 'primevue/steplist'
import StepPanels from 'primevue/steppanels'
import Step from 'primevue/step'
import StepPanel from 'primevue/steppanel'
import UploadData from '../../ui/UploadData.vue'
import ServiceEvaluate from './third-step/ServiceEvaluate.vue'
import TableView from '@/components/table-view/index.vue'
import UiTraining from '@/components/ui/UiTraining.vue'
import { useRouteLeaveConfirm } from '@/hooks/useRouteLeaveConfirm'
import { dashboardFinishConfirmOptions } from '@/lib/primevue/data/confirm'

type Step = {
  id: number
  text: string
}

type TProps = {
  steps: Step[]
  task: Tasks
}

const { setGuard } = useRouteLeaveConfirm(dashboardFinishConfirmOptions(() => {}))

const props = defineProps<TProps>()

const tableValidator = (size?: number, columns?: number, rows?: number) => {
  return {
    size: !!(size && size > 50 * 1024 * 1024),
    columns: !!(columns && columns <= 3),
    rows: !!(rows && rows <= 100),
  }
}

const {
  isTableExist,
  fileData,
  uploadDataErrors,
  isUploadWithErrors,
  columnsCount,
  rowsCount,
  getAllColumnNames,
  viewValues,
  getTarget,
  getGroup,
  selectedColumns,
  getFilters,
  columnTypes,
  onSelectFile,
  onRemoveFile,
  setTarget,
  changeGroup,
  setSelectedColumns,
  downloadCSV,
  setFilters,
  getDataForTraining,
} = useDataTable(tableValidator)
const {
  isLoading,
  startTraining: startModelTraining,
  isTrainingSuccess,
  getTotalScore,
  getTestMetrics,
  getTrainingMetrics,
  getTop5Feature,
  getPredictedData,
  isTrainMode,
  trainingModelId,
  currentTask,
  modelBlob,
  downloadModel,
} = useModelTraining('tabular')

const currentStep = ref(1)
const sampleFileName = computed(() =>
  props.task === Tasks.TABULAR_CLASSIFICATION ? 'iris.csv' : 'insurance.csv',
)
const resources = computed(() =>
  props.task === Tasks.TABULAR_CLASSIFICATION ? classificationResources : regressionResources,
)
const isStepAvailable = computed(() => (id: number) => {
  if (currentStep.value === 3) return

  if (id === 1) return true
  else if (id === 2) return isTableExist.value && !isUploadWithErrors.value
  else if (id === 3) return false
})
const getPredictionFields = computed(() => {
  const columns = selectedColumns.value.length ? selectedColumns.value : getAllColumnNames.value
  return columns.filter((column) => column !== getTarget.value)
})

async function startTraining() {
  const data = getDataForTraining()
  const target = getTarget.value
  const task = props.task
  await startModelTraining({ data, target, task })

  if (isTrainingSuccess.value) {
    currentStep.value = 3
  }
}

watch(
  currentStep,
  (value) => {
    setGuard(value === 3)
  },
  { immediate: true },
)
</script>

<style scoped>
.stepper {
  padding-top: 32px;
}

.steppanels {
  padding: 0;
}

.navigation {
  display: flex;
  gap: 24px;
  justify-content: flex-end;
}

@media (max-height: 1050px) {
  .navigation {
    position: fixed;
    bottom: 0;
    right: 0;
    background-color: var(--p-content-background);
    padding-top: 4px;
    padding-bottom: 44px;
    padding-right: 105px;
    width: 100%;
    z-index: 5;
  }
}

@media (max-width: 968px) {
  .navigation {
    position: fixed;
    bottom: 0;
    right: 0;
    background-color: var(--p-content-background);
    padding-top: 4px;
    padding-bottom: 44px;
    padding-right: 105px;
    width: 100%;
    z-index: 5;
  }
}

@media (max-width: 768px) {
  .stepper {
    padding-top: 16px;
  }
  .step-label {
    display: none;
  }
  .navigation {
    padding-right: 15px;
  }
}
</style>
