import type {
  AddAnnotationPayload,
  Annotation,
  UpdateAnnotationPayload,
} from '@/components/annotations/annotations.interface'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { useEvalsStore } from './evals'
import type { AddEvalAnnotationParams, AddSpanAnnotationParams } from './annotations.interface'

export const useAnnotationsStore = defineStore('annotations', () => {
  const evalStore = useEvalsStore()

  const isEditAvailable = ref(false)

  const addAnnotationData = ref<AddEvalAnnotationParams | AddSpanAnnotationParams | null>(null)

  const evalAnnotations = ref<Annotation[]>([])

  const spanAnnotations = ref<Annotation[]>([])

  const isAddDialogVisible = computed(() => {
    return !!addAnnotationData.value
  })

  function allowEdit() {
    isEditAvailable.value = true
  }

  function disallowEdit() {
    isEditAvailable.value = false
  }

  function openAddDialog(params: AddEvalAnnotationParams | AddSpanAnnotationParams) {
    addAnnotationData.value = params
  }

  function closeAddDialog() {
    addAnnotationData.value = null
  }

  async function addEvalAnnotation(data: AddAnnotationPayload) {
    const provider = evalStore.getProvider

    if (!provider.createEvalAnnotation) {
      throw new Error('Create annotation method is not available')
    }

    if (!addAnnotationData.value) {
      throw new Error('Add annotation data is not set')
    }

    const { artifactId, datasetId, evalId } = addAnnotationData.value as AddEvalAnnotationParams

    if (!artifactId || !datasetId || !evalId) {
      throw new Error('Artifact ID, dataset ID and eval ID are required')
    }

    const response = await provider.createEvalAnnotation(artifactId, datasetId, evalId, data)
    evalAnnotations.value.push(response)
  }

  async function updateEvalAnnotation(
    artifactId: string,
    annotationId: string,
    data: UpdateAnnotationPayload,
  ) {
    const provider = evalStore.getProvider

    if (!provider.updateEvalAnnotation) {
      throw new Error('Update annotation method is not available')
    }

    const response = await provider.updateEvalAnnotation(artifactId, annotationId, data)
    const index = evalAnnotations.value.findIndex((item) => item.id === annotationId)
    if (index !== -1) {
      evalAnnotations.value[index] = response
    }
  }

  async function getEvalAnnotations(artifactId: string, datasetId: string, evalId: string) {
    evalAnnotations.value = await evalStore.getProvider.getEvalAnnotations(
      artifactId,
      datasetId,
      evalId,
    )
  }

  async function deleteEvalAnnotation(artifactId: string, annotationId: string) {
    const provider = evalStore.getProvider

    if (!provider.deleteEvalAnnotation) {
      throw new Error('Delete annotation method is not available')
    }

    await provider.deleteEvalAnnotation(artifactId, annotationId)
    const index = evalAnnotations.value.findIndex((item) => item.id === annotationId)
    if (index !== -1) {
      evalAnnotations.value.splice(index, 1)
    }
  }

  async function getEvalsDatasetAnnotationsSummary(datasetId: string) {
    return evalStore.getProvider.getEvalsDatasetAnnotationsSummary(datasetId)
  }

  async function addSpanAnnotation(data: AddAnnotationPayload) {
    const provider = evalStore.getProvider
    if (!provider.createSpanAnnotation) {
      throw new Error('Create span annotation method is not available')
    }
    if (!addAnnotationData.value) {
      throw new Error('Add annotation data is not set')
    }

    const { artifactId, traceId, spanId } = addAnnotationData.value as AddSpanAnnotationParams

    if (!artifactId || !traceId || !spanId) {
      throw new Error('Artifact ID, trace ID and span ID are required')
    }
    const response = await provider.createSpanAnnotation(artifactId, traceId, spanId, data)
    spanAnnotations.value.push(response)
  }

  async function updateSpanAnnotation(
    artifactId: string,
    annotationId: string,
    data: UpdateAnnotationPayload,
  ) {
    const provider = evalStore.getProvider
    if (!provider.updateSpanAnnotation) {
      throw new Error('Update span annotation method is not available')
    }
    const response = await provider.updateSpanAnnotation(artifactId, annotationId, data)
    const index = spanAnnotations.value.findIndex((item) => item.id === annotationId)
    if (index !== -1) {
      spanAnnotations.value[index] = response
    }
  }

  async function getSpanAnnotations(artifactId: string, traceId: string, spanId: string) {
    spanAnnotations.value = await evalStore.getProvider.getSpanAnnotations(
      artifactId,
      traceId,
      spanId,
    )
  }

  async function deleteSpanAnnotation(artifactId: string, annotationId: string) {
    const provider = evalStore.getProvider
    if (!provider.deleteSpanAnnotation) {
      throw new Error('Delete span annotation method is not available')
    }
    await provider.deleteSpanAnnotation(artifactId, annotationId)
    const index = spanAnnotations.value.findIndex((item) => item.id === annotationId)
    if (index !== -1) {
      spanAnnotations.value.splice(index, 1)
    }
  }

  async function getTracesAnnotationSummary(artifactId: string) {
    return evalStore.getProvider.getTracesAnnotationSummary(artifactId)
  }

  return {
    isEditAvailable,
    allowEdit,
    disallowEdit,
    isAddDialogVisible,
    openAddDialog,
    closeAddDialog,
    addEvalAnnotation,
    updateEvalAnnotation,
    getEvalAnnotations,
    evalAnnotations,
    deleteEvalAnnotation,
    getEvalsDatasetAnnotationsSummary,
    addSpanAnnotation,
    updateSpanAnnotation,
    getSpanAnnotations,
    deleteSpanAnnotation,
    getTracesAnnotationSummary,
    spanAnnotations,
  }
})
