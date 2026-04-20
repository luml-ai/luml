<template>
  <div class="prompt-fusion-page">
    <div v-if="step === 1">
      <upload-data
        :errors="uploadDataErrors"
        :is-table-exist="isTableExist"
        :file="fileData"
        :min-columns-count="2"
        :min-rows-count="10"
        :resources="promptFusionResources"
        sample-file-name="formal-phrases.csv"
        @selectFile="selectFile"
        @removeFile="onRemoveFile"
      />
      <first-step-navigation
        :is-next-step-available="!!fileData.name && !isUploadWithErrors"
        @continue="step = 2"
      />
    </div>
    <step-edit
      v-else-if="step === 2 && columnsCount && rowsCount && viewValues"
      @back="step = 1"
      @continue="goToMainStep"
    >
      <table-view
        :columns-count="columnsCount"
        :rows-count="rowsCount"
        :all-columns="getAllColumnNames"
        :value="viewValues"
        :selected-columns="selectedColumns"
        :export-callback="downloadCSV"
        :columnTypes="columnTypes"
        :inputs-outputs-columns="inputsOutputsColumns"
        show-column-header-menu
        @edit="setSelectedColumns"
        :target="getTarget"
        :group="getGroup"
        @set-target="setTarget"
        @change-group="changeGroup"
      />
    </step-edit>
    <step-main v-else-if="step === 3" :initial-nodes="initialNodes" @go-back="backFromMain" />
  </div>
</template>

<script setup lang="ts">
import type { PromptNode } from '@/components/express-tasks/prompt-fusion/interfaces'
import { nextTick, onBeforeMount, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDataTable } from '@/hooks/useDataTable'
import { promptFusionResources } from '@/constants/constants'
import { getInitialNodes, getSample } from '@/constants/prompt-fusion'
import { promptFusionService } from '@/lib/promt-fusion/PromptFusionService'
import { useVueFlow } from '@vue-flow/core'
import FirstStepNavigation from '@/components/express-tasks/prompt-fusion/step-upload/Navigation.vue'
import TableView from '@/components/table-view/index.vue'
import StepEdit from '@/components/express-tasks/prompt-fusion/step-edit/StepEdit.vue'
import StepMain from '@/components/express-tasks/prompt-fusion/step-main/index.vue'
import UploadData from '@/components/ui/UploadData.vue'

const { $reset, addEdges, addNodes, toObject } = useVueFlow()

const tableValidator = (size?: number, columns?: number, rows?: number) => {
  return {
    size: !!(size && size > 50 * 1024 * 1024),
    columns: !!(columns && columns <= 1),
    rows: !!(rows && rows <= 10),
  }
}

const route = useRoute()
const router = useRouter()
const {
  isTableExist,
  fileData,
  uploadDataErrors,
  isUploadWithErrors,
  columnsCount,
  rowsCount,
  getAllColumnNames,
  viewValues,
  selectedColumns,
  columnTypes,
  inputsOutputsColumns,
  getInputsColumns,
  getOutputsColumns,
  getTarget,
  getGroup,
  setTarget,
  changeGroup,
  onSelectFile,
  onRemoveFile,
  setSelectedColumns,
  downloadCSV,
  getDataForTraining,
} = useDataTable(tableValidator)

const step = ref<number>()
const initialNodes = ref<PromptNode[]>([])
const isSampleDataset = ref(false)

function backFromMain() {
  if (route.params.mode === 'data-driven') step.value = 2
  else router.back()
}
function goToMainStep() {
  promptFusionService.saveTrainingData(
    getDataForTraining() as Record<string, []>,
    getInputsColumns.value,
    getOutputsColumns.value,
  )
  step.value = 3
  nextTick(() => {
    if (isSampleDataset.value) {
      const sample = getSample(getInputsColumns.value, getOutputsColumns.value)
      addNodes(sample.nodes)
      addEdges(sample.edges)
    } else {
      addNodes(getInitialNodes())
    }
  })
}
function selectFile(file: File) {
  onSelectFile(file)
  isSampleDataset.value = file.name === 'formal-phrases.csv'
}

onBeforeMount(() => {
  step.value = route.params.mode === 'data-driven' ? 1 : 3
})
onMounted(() => {
  if (step.value === 3) {
    addNodes(getInitialNodes())
  }
})
onBeforeUnmount(() => {
  $reset()
  promptFusionService.resetState()
})
</script>

<style scoped></style>
