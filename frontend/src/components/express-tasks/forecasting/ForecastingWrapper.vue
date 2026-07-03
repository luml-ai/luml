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
          :min-columns-count="2"
          :min-rows-count="30"
          :resources="forecastingResources"
          sample-file-name="retail_sales.csv"
          @selectFile="onSelectFile"
          @removeFile="onRemoveFile"
        />
        <div class="navigation">
          <d-button label="Back" severity="secondary" @click="$router.push({ name: 'home' })" />
          <d-button
            data-testid="forecasting-continue"
            :disabled="!isStepAvailable(2)"
            @click="activateCallback(2)"
          >
            <span style="font-weight: 500">Continue</span>
            <arrow-right width="14" height="14" />
          </d-button>
        </div>
      </StepPanel>
      <StepPanel v-slot="{ activateCallback }" :value="2">
        <forecast-setup
          v-if="currentStep === 2 && viewValues"
          :columns="getAllColumnNames"
          :rows="viewValues as Record<string, unknown>[]"
          @change="onSetupChange"
        />
        <div class="navigation">
          <d-button label="Back" severity="secondary" @click="activateCallback(1)" />
          <d-button
            data-testid="forecasting-train"
            :disabled="!setupState?.isValid"
            @click="startTraining"
          >
            <span style="font-weight: 500">Train</span>
            <arrow-right width="14" height="14" />
          </d-button>
        </div>
      </StepPanel>
      <StepPanel :value="3">
        <forecasting-evaluate v-if="currentStep === 3 && evaluateProps" v-bind="evaluateProps" />
      </StepPanel>
    </StepPanels>
  </Stepper>
  <ui-training v-model="isLoading" :time="8" />
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type {
  Tasks,
  ForecastingRecord,
  ForecastingTrainPayload,
  ForecastingTrainingTable,
} from '@/lib/data-processing/interfaces'
import type { ForecastSetupState } from '@/lib/data-processing/forecasting-setup'
import { useDataTable } from '@/hooks/useDataTable'
import { useForecastingTraining } from '@/hooks/useForecastingTraining'
import { forecastingResources } from '@/constants/constants'
import { ArrowRight } from 'lucide-vue-next'
import Stepper from 'primevue/stepper'
import StepList from 'primevue/steplist'
import StepPanels from 'primevue/steppanels'
import Step from 'primevue/step'
import StepPanel from 'primevue/steppanel'
import UploadData from '@/components/ui/UploadData.vue'
import ForecastSetup from './ForecastSetup.vue'
import ForecastingEvaluate from './evaluate/index.vue'
import UiTraining from '@/components/ui/UiTraining.vue'
import { useRouteLeaveConfirm } from '@/hooks/useRouteLeaveConfirm'
import { dashboardFinishConfirmOptions } from '@/lib/primevue/data/confirm'

type Step = {
  id: number
  text: string
}

type TProps = {
  steps: Step[]
  task: Tasks.FORECASTING
}

defineProps<TProps>()

const { setGuard } = useRouteLeaveConfirm(dashboardFinishConfirmOptions(() => {}))

const tableValidator = (size?: number, columns?: number, rows?: number) => {
  return {
    size: !!(size && size > 50 * 1024 * 1024),
    columns: !!(columns && columns < 2),
    rows: !!(rows && rows < 30),
  }
}

const {
  isTableExist,
  fileData,
  uploadDataErrors,
  isUploadWithErrors,
  getAllColumnNames,
  viewValues,
  onSelectFile,
  onRemoveFile,
  getDataForTraining,
} = useDataTable(tableValidator)

const {
  isLoading,
  isTrainingSuccess,
  trainingData,
  trainingModelId,
  getTotalScore,
  startTraining: startForecastTraining,
  startPredict,
  downloadModel,
} = useForecastingTraining()

const currentStep = ref(1)
const setupState = ref<ForecastSetupState | null>(null)
const historyRecords = ref<ForecastingRecord[]>([])

const isStepAvailable = (id: number) => {
  if (currentStep.value === 3) return false

  if (id === 1) return true
  else if (id === 2) return isTableExist.value && !isUploadWithErrors.value
  else return false
}

const evaluateProps = computed(() => {
  const data = trainingData.value
  if (!data || !trainingModelId.value) return null
  return {
    totalScore: getTotalScore.value,
    testMetrics: data.test_metrics,
    trainMetrics: data.train_metrics,
    modelConfig: data.model_config,
    chart: data.chart,
    history: historyRecords.value,
    modelId: trainingModelId.value,
    predict: startPredict,
    downloadModel,
  }
})

function onSetupChange(state: ForecastSetupState) {
  setupState.value = state
}

function tableToRecords(table: ForecastingTrainingTable): ForecastingRecord[] {
  const columns = Object.keys(table)
  const length = columns.length ? table[columns[0]].length : 0
  return Array.from({ length }, (_, i) =>
    Object.fromEntries(columns.map((col) => [col, table[col][i]])),
  )
}

async function startTraining() {
  if (!setupState.value?.isValid) return

  const data = getDataForTraining()
  historyRecords.value = tableToRecords(data)
  const payload: ForecastingTrainPayload = {
    data,
    ...setupState.value.config,
  }
  await startForecastTraining(payload)

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
