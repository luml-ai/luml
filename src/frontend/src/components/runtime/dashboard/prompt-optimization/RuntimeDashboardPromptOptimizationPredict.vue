<template>
  <div class="content" :class="{ disabled: loading }">
    <p class="text">Get predictions by entering data manually or uploading a dataset</p>
    <SelectButton v-model="selectValue" :options="selectOptions" />
    <div v-if="selectValue === 'Manual'" class="manual">
      <div class="inputs">
        <div v-for="field in Object.keys(manualValues)" :key="field" class="input-wrapper">
          <FloatLabel variant="on">
            <InputText
              v-model="manualValues[field as keyof typeof manualValues]"
              :id="field"
              fluid
            />
            <label class="label" :for="field">{{ cutStringOnMiddle(field, 24) }}</label>
          </FloatLabel>
        </div>
      </div>
      <Button
        label="Predict"
        type="submit"
        fluid
        :disabled="isManualPredictButtonDisabled"
        @click="onManualSubmit"
      />
      <Textarea
        class="prediction"
        v-model="predictionText"
        id="prediction"
        fluid
        rows="4"
        :style="{ resize: 'none' }"
        disabled
        placeholder="Prediction"
      ></Textarea>
    </div>
    <div v-else class="upload">
      <FileInput
        id="predict"
        :file="fileData"
        :error="isUploadWithErrors || filePredictWithError"
        :loading="loading"
        loading-message="Loading prediction..."
        :success-message-only="
          predictReadyForDownload ? 'Success! Your predictions are ready—download the file.' : ''
        "
        success-remove-text="Upload new dataset"
        :accept="['text/csv']"
        accept-text="Supports CSV file format"
        upload-text="upload CSV"
        @select-file="onSelectFile"
        @remove-file="onRemoveFile"
      />
      <Button
        v-if="predictReadyForDownload"
        label="Download"
        type="submit"
        fluid
        @click="downloadPredict"
      />
      <Button
        v-else
        label="Predict"
        type="submit"
        fluid
        :disabled="isPredictButtonDisabled"
        @click="onFileSubmit"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { SelectButton, FloatLabel, InputText, Button, Textarea, useToast } from 'primevue'
import FileInput from '@/components/ui/FileInput.vue'
import { computed, ref } from 'vue'
import { convertObjectToCsvBlob, cutStringOnMiddle, downloadFileFromBlob } from '@/helpers/helpers'
import { AnalyticsService, AnalyticsTrackKeysEnum } from '@/lib/analytics/AnalyticsService'
import { useDataTable } from '@/hooks/useDataTable'
import { DataProcessingWorker } from '@/lib/data-processing/DataProcessingWorker'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'

type Props = {
  manualFields: string[]
  modelId: string
  dynamicAttributes: Record<string, string | number>
  providerConnected: boolean
}

const tableValidator = () => {
  return { size: false, columns: false, rows: false }
}
const { isUploadWithErrors, fileData, onSelectFile, getDataForTraining, onRemoveFile } =
  useDataTable(tableValidator)

const toast = useToast()

const props = defineProps<Props>()

const loading = ref(false)

const selectOptions = ref(['Manual', 'Upload file'])
const selectValue = ref<'Manual' | 'Upload file'>('Manual')
const manualValues = ref(Object.fromEntries(props.manualFields.map((field) => [field, ''])))
const predictionText = ref('')
const filePredictWithError = ref(false)
const downloadPredictBlob = ref<Blob | null>(null)

const isManualPredictButtonDisabled = computed(() => {
  return Object.values(manualValues.value).some((value) => !value) || !props.providerConnected
})
const predictReadyForDownload = computed(() => !!downloadPredictBlob.value)
const isPredictButtonDisabled = computed(
  () => !fileData.value.name || isUploadWithErrors.value || !props.providerConnected,
)

async function onManualSubmit() {
  loading.value = true
  try {
    sendAnalytics()
    predictionText.value = ''
    const data = prepareManualData()
    const payload = getPredictPayload(data)
    const result = await DataProcessingWorker.computePythonModel(payload)
    if (result?.status === 'success') {
      predictionText.value = JSON.stringify(result.predictions?.out)
    } else if (result.status === 'error') {
      throw new Error(result.error_message)
    }
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : 'Unknown Error'
    toast.add(simpleErrorToast(message))
  } finally {
    loading.value = false
  }
}

async function onFileSubmit() {
  loading.value = true
  filePredictWithError.value = false
  try {
    sendAnalytics()
    const data = getDataForTraining()
    const formattedData = Object.fromEntries(
      Object.entries(data).map(([key, value]) => {
        return [key, value[0]]
      }),
    )
    const payload = getPredictPayload(formattedData)
    const result = await DataProcessingWorker.computePythonModel(payload)
    if (result?.status === 'success') {
      const object: Record<string, string | number | object> = {
        inputs: [formattedData],
        prediction: [result.predictions?.out],
      }
      downloadPredictBlob.value = convertObjectToCsvBlob(object)
    } else if (result.status === 'error') {
      throw new Error(result.error_message)
    }
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : 'Unknown Error'
    toast.add(simpleErrorToast(message))
    filePredictWithError.value = true
  } finally {
    loading.value = false
  }
}

function prepareManualData() {
  const data: Record<string, string | number> = {}
  for (const key in manualValues.value) {
    const value = manualValues.value[key].trim()
    if (!value) continue
    const formattedValue = isNaN(Number(value)) ? value : Number(value)
    data[key] = formattedValue
  }
  return data
}

function getPredictPayload(data: Record<string, string | number>) {
  return {
    inputs: { in: data },
    model_id: props.modelId,
    dynamic_attributes: props.dynamicAttributes,
  }
}

function downloadPredict() {
  if (!downloadPredictBlob.value) return
  downloadFileFromBlob(downloadPredictBlob.value, 'dfs-predictions')
}

function sendAnalytics() {
  AnalyticsService.track(AnalyticsTrackKeysEnum.predict, { task: 'prompt_optimization_runtime' })
}
</script>

<style scoped>
.text {
  margin-bottom: 28px;
  color: var(--p-text-muted-color);
}

.manual {
  display: flex;
  flex-direction: column;
  gap: 28px;
}

.upload {
  display: flex;
  flex-direction: column;
  gap: 28px;
  margin-top: 28px;
}

.inputs {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-height: 306px;
  overflow-y: auto;
  padding-top: 14px;
  margin-top: 14px;
}

.disabled {
  opacity: 0.6;
  pointer-events: none;
}

.prediction:disabled {
  background-color: var(--p-textarea-background) !important;
  color: var(--p-textarea-color);
}

.prediction.p-filled {
  border: 1px solid var(--p-textarea-focus-border-color);
  background-color: var(--p-textarea-filled-background) !important;
  font-weight: 500 !important;
}
</style>
