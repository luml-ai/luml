<template>
  <div class="wrapper">
    <file-input
      id="predict"
      :file="fileData"
      :error="isUploadWithErrors || filePredictWithError"
      :loading="isLoading"
      loading-message="Loading prediction..."
      :success-message-only="
        isPredictReadyForDownload ? 'Success! Your predictions are ready—download the file.' : ''
      "
      success-remove-text="Upload new dataset"
      :accept="['text/csv']"
      accept-text="Supports CSV file format"
      upload-text="upload CSV"
      @select-file="onSelectFile"
      @remove-file="onRemoveFile"
    />
    <d-button
      v-if="isPredictReadyForDownload"
      label="Download"
      type="submit"
      fluid
      rounded
      @click="downloadPredict"
    />
    <d-button
      v-else
      label="Predict"
      type="submit"
      fluid
      :disabled="isPredictButtonDisabled"
      rounded
      @click="submit"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import FileInput from '@/components/ui/FileInput.vue'
import { useDataTable } from '@/hooks/useDataTable'
import { convertObjectToCsvBlob } from '@/helpers/helpers'
import { predictErrorToast } from '@/lib/primevue/data/toasts'
import { useToast } from 'primevue'

const toast = useToast()

type Props = {
  predictCallback: Function
}

const props = defineProps<Props>()

const tableValidator = () => ({
  size: false,
  columns: false,
  rows: false,
})
const { isUploadWithErrors, fileData, onSelectFile, getDataForTraining, onRemoveFile } =
  useDataTable(tableValidator)

const filePredictWithError = ref(false)
const isLoading = ref(false)
const downloadPredictBlob = ref<Blob | null>(null)

const isPredictReadyForDownload = computed(() => !!downloadPredictBlob.value)
const isPredictButtonDisabled = computed(
  () => !fileData.value.name || !isUploadWithErrors || isLoading.value,
)

async function submit() {
  isLoading.value = true
  const data = getDataForTraining()
  try {
    const result = await props.predictCallback(data)
    downloadPredictBlob.value = convertObjectToCsvBlob(result)
  } catch (e) {
    toast.add(predictErrorToast(e as string))
    filePredictWithError.value = true
  } finally {
    isLoading.value = false
  }
}
function downloadPredict() {
  if (!downloadPredictBlob.value) return
  const url = URL.createObjectURL(downloadPredictBlob.value)
  const a = document.createElement('a')
  a.href = url
  a.download = 'dfs-predictions'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

watch(
  fileData,
  () => {
    filePredictWithError.value = false
    downloadPredictBlob.value = null
  },
  { deep: true },
)
</script>

<style scoped>
.wrapper {
  display: flex;
  flex-direction: column;
  gap: 28px;
}
</style>
