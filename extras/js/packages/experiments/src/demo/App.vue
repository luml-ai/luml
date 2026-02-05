<template>
  <div class="app">
    <div class="app-header">
      <h1 class="app-title">Luml Experiment Demo</h1>
      <input type="file" multiple @change="handleFileChange" />
      <Button label="Toggle Theme" @click="toggleTheme" />
    </div>
    <ExperimentSnapshot
      v-if="provider"
      :theme="theme"
      :provider="provider"
      :models-ids="Object.keys(modelsInfo)"
      :models-info="modelsInfo"
    />
  </div>
  <Toast position="top-right" />
</template>

<script setup lang="ts">
import type { ExperimentSnapshotProvider, ModelInfo } from '@/interfaces/interfaces'
import type { Model } from '@fnnx/web'
import { ref } from 'vue'
import { Button, Toast } from 'primevue'
import { FnnxService } from './lib/fnnx/FnnxService'
import { ExperimentSnapshotDatabaseProvider } from '@/providers/ExperimentSnapshotDatabaseProvider'
import { getModelColorByIndex } from '@/helpers/helpers'
import ExperimentSnapshot from '@/ExperimentSnapshot.vue'

const modelsInfo = ref<Record<string, ModelInfo>>({})
const provider = ref<ExperimentSnapshotProvider | null>(null)

const theme = ref<'light' | 'dark'>('light')

function toggleTheme() {
  theme.value = theme.value === 'light' ? 'dark' : 'light'
  document.documentElement.dataset.theme = theme.value
}

async function handleFileChange(event: Event) {
  reset()
  const files = (event.target as HTMLInputElement).files
  if (!files) {
    reset()
    return
  }
  try {
    checkFiles(Array.from(files))
    const models = await createModels(Array.from(files))
    const experiments = getModelsExperimentsInfo(models)
    if (experiments.length === 0) throw new Error('No experiments found')
    const fileNames = Array.from(files).map((file) => file.name)
    setModelsInfo(
      experiments.map((experiment) => experiment.modelId),
      fileNames,
    )
    const currentProvider = new ExperimentSnapshotDatabaseProvider()
    await currentProvider.init(experiments, { wasmUrl: '/sql-wasm.wasm' })
    provider.value = currentProvider
  } catch (e) {
    console.error(e)
    reset()
  }
}

function checkFiles(files: File[]) {
  const allowedExtensions = ['.fnnx', '.pyfnx', '.dfs', '.luml']
  const isAllowed = files.every((file) => allowedExtensions.some((ext) => file.name.endsWith(ext)))
  if (!isAllowed) throw new Error('Incorrect file format')
}

function createModels(files: File[]) {
  return Promise.all(files.map((file) => FnnxService.createModelFromFile(file)))
}

function getModelsExperimentsInfo(models: Model[]): { modelId: string; buffer: ArrayBuffer }[] {
  return models
    .map((model, index) => {
      const unit8Array = FnnxService.findExperimentSnapshotArchive((model as any).modelFiles)
      return {
        modelId: `model-${index}`,
        buffer: unit8Array as any,
      }
    })
    ?.filter((info) => info.buffer) as { modelId: string; buffer: ArrayBuffer }[]
}

function setModelsInfo(modelIds: string[], names: string[]) {
  modelsInfo.value = modelIds.reduce(
    (acc, modelId, index) => {
      acc[modelId] = {
        name: names[index] || modelId,
        color: getModelColorByIndex(index),
      }
      return acc
    },
    {} as Record<string, ModelInfo>,
  )
}

function reset() {
  modelsInfo.value = {}
  provider.value = null
}
</script>

<style scoped>
.app {
  padding: 15px;
}

.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.app-title {
  margin-bottom: 20px;
}
</style>
