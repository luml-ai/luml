<template>
  <div>
    <d-dialog
      v-model:visible="isPredictVisible"
      modal
      header="Predict"
      :style="{ width: '31.25rem' }"
    >
      <predict-content
        :manual-fields="predictionFields"
        :model-id="trainingModelId"
        :task="taskName"
      />
    </d-dialog>
    <header class="header">
      <h1 class="title">Model Evaluation Dashboard</h1>
      <div class="buttons">
        <d-button severity="secondary" @click="isPredictVisible = true">
          <span>predict</span>
          <wand-sparkles width="14" height="14" />
        </d-button>
        <SplitButton
          label="export"
          severity="secondary"
          @click="onDownloadClick"
          :model="EXPORT_ITEMS"
        />
        <d-button label="finish" @click="finishConfirm" />
      </div>
    </header>
    <div class="body">
      <ModelTabularPerformance
        v-if="currentTask"
        :total-score="totalScore"
        :test-metrics="testMetrics"
        :training-metrics="trainingMetrics"
        :tag="producedTag"
        class="performance"
      ></ModelTabularPerformance>
      <div class="features card">
        <header class="card-header">
          <h3 class="card-title">Top {{ features.length }} features</h3>
          <info
            width="20"
            height="20"
            class="info-icon"
            v-tooltip.bottom="
              `Understand which features play the biggest role in your model's outcomes to guide further data analysis`
            "
          />
        </header>
        <div :style="{ maxWidth: '725px' }">
          <apexchart
            type="bar"
            :options="featuresOptions"
            :series="featuresData"
            :height="barChartHeight"
            width="100%"
            :style="{ pointerEvents: 'none', margin: '-30px 0' }"
          />
        </div>
      </div>
      <div class="detailed card">
        <detailed-table :values="detailedView" :is-train-mode="isTrainMode" />
      </div>
    </div>
  </div>
  <ModelUpload
    v-if="modelBlob && currentTask && !!organizationStore.currentOrganization"
    :model-blob="modelBlob"
    :current-task="currentTask"
    v-model:visible="modelUploadVisible"
  ></ModelUpload>
</template>

<script setup lang="ts">
import { Tasks, type TrainingImportance } from '@/lib/data-processing/interfaces'
import { computed, onBeforeMount, ref } from 'vue'
import { WandSparkles, Info } from 'lucide-vue-next'
import { getBarOptions } from '@/lib/apex-charts/apex-charts'
import { table } from 'arquero'
import { useConfirm } from 'primevue/useconfirm'
import { dashboardFinishConfirmOptions } from '@/lib/primevue/data/confirm'
import { useRouter } from 'vue-router'
import DetailedTable from './DetailedTable.vue'
import PredictContent from '@/components/predict/index.vue'
import { AnalyticsService, AnalyticsTrackKeysEnum } from '@/lib/analytics/AnalyticsService'
import { SplitButton } from 'primevue'
import ModelUpload from '@/components/model-upload/ModelUpload.vue'
import { useOrganizationStore } from '@/stores/organization'
import ModelTabularPerformance from '@/components/model/ModelTabularPerformance.vue'
import { FNNX_PRODUCER_TAGS_MANIFEST_ENUM } from '@/lib/fnnx/FnnxService'

type Props = {
  predictionFields: string[]
  totalScore: number
  testMetrics: string[]
  trainingMetrics: string[]
  features: TrainingImportance[]
  predictedData: Record<string, []>
  isTrainMode: boolean
  downloadModelCallback: Function
  trainingModelId: string
  currentTask: Tasks | null
  modelBlob: Blob | null
}

const props = defineProps<Props>()

const router = useRouter()
const confirm = useConfirm()
const organizationStore = useOrganizationStore()

const modelUploadVisible = ref(false)

const EXPORT_ITEMS = [
  {
    label: 'Upload to Registry',
    command: () => {
      modelUploadVisible.value = true
    },
    disabled: () => !organizationStore.currentOrganization,
  },
  {
    label: 'Download model',
    command: () => {
      onDownloadClick()
    },
  },
]

const isPredictVisible = ref(false)
const detailedView = ref<any>([])

const featuresData = computed(() => {
  const data = props.features.map((feature) => (feature.scaled_importance * 100).toFixed())
  return [{ data }]
})
const featuresOptions = computed(() =>
  getBarOptions(
    props.features.map((feature) => {
      const name =
        feature.feature_name.length > 12
          ? feature.feature_name.slice(0, 10) + '...'
          : feature.feature_name
      return `${name} (${(feature.scaled_importance * 100).toFixed()}%)`
    }),
  ),
)
const barChartHeight = computed(() => {
  const featuresCount = props.features.length
  return 45 * featuresCount + 60 + 'px'
})
const taskName = computed(() =>
  props.currentTask === Tasks.TABULAR_CLASSIFICATION ? 'classification' : 'regression',
)
const producedTag = computed(() =>
  props.currentTask === Tasks.TABULAR_CLASSIFICATION
    ? FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_classification_v1
    : FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_regression_v1,
)

function onDownloadClick() {
  props.downloadModelCallback()
  if (props.currentTask) {
    AnalyticsService.track(AnalyticsTrackKeysEnum.download, { task: taskName.value })
  }
}

const finishConfirm = () => {
  if (props.currentTask) {
    AnalyticsService.track(AnalyticsTrackKeysEnum.finish, { task: taskName.value })
  }
  const accept = async () => {
    router.push({ name: 'home' })
  }
  confirm.require(dashboardFinishConfirmOptions(accept))
}

onBeforeMount(() => {
  detailedView.value = table(props.predictedData).objects()
})
</script>

<style scoped>
.header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding-top: 32px;
  margin-bottom: 20px;
}

.title {
  font-size: 24px;
}

.buttons {
  display: flex;
  gap: 8px;
}

.body {
  display: grid;
  grid-template-columns: 374px 1fr;
  gap: 24px;
}

.card {
  padding: 24px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  border-radius: 8px;
  box-shadow: var(--card-shadow);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.card-title {
  font-size: 20px;
}

.info-icon {
  color: var(--p-icon-muted-color);
}

.performance {
  grid-row: span 2;
}

@media (max-width: 1200px) {
  .header {
    flex-direction: column;
  }

  .body {
    grid-template-columns: 1fr;
  }

  .metric-cards {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .header {
    padding-top: 8px;
  }
  .card {
    padding: 16px;
  }
  .metric-cards {
    grid-template-columns: 1fr;
  }
  .info-icon {
    display: none;
  }
}
</style>
