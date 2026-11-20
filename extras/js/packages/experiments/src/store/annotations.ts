import type {
  AddAnnotationPayload,
  Annotation,
  AnnotationSummary,
  UpdateAnnotationPayload,
} from '@/components/annotations/annotations.interface'
import type { AddEvalAnnotationParams, AddSpanAnnotationParams } from './annotations.interface'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { useEvalsStore } from './evals/index'
import { useTraceStore } from './trace'
import { isEmpty } from '@/helpers/helpers'

export const useAnnotationsStore = defineStore('annotations', () => {
  const evalStore = useEvalsStore()
  const traceStore = useTraceStore()

  const isEditAvailable = ref(false)

  const addAnnotationData = ref<AddEvalAnnotationParams | AddSpanAnnotationParams | null>(null)

  const evalsAnnotationsSummaryByDatasetId = ref<Record<string, AnnotationSummary>>({})

  const tracesAnnotationsSummary = ref<AnnotationSummary | null>(null)

  const evalAnnotations = ref<Annotation[]>([])

  const spanAnnotations = ref<Annotation[]>([])

  // The latest read per key: an older answer arriving later, from a view that moved on or
  // closed, must not replace it.
  const latestReads = new Map<string, object>()

  async function readLatest<T>(key: string, read: () => Promise<T>, apply: (value: T) => void) {
    const request = {}
    latestReads.set(key, request)
    const value = await read()
    if (latestReads.get(key) === request) apply(value)
  }

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

    if (isEmpty(artifactId) || isEmpty(datasetId) || isEmpty(evalId)) {
      throw new Error('Artifact ID, dataset ID and eval ID are required')
    }

    const response = await provider.createEvalAnnotation(artifactId, datasetId, evalId, data)
    evalAnnotations.value.push(response)
    await evalStore.initDataset(datasetId)
  }

  async function updateEvalAnnotation(
    artifactId: string,
    datasetId: string,
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
    await evalStore.initDataset(datasetId)
  }

  async function getEvalAnnotations(artifactId: string, datasetId: string, evalId: string) {
    await readLatest(
      'evalAnnotations',
      () => evalStore.getProvider.getEvalAnnotations(artifactId, datasetId, evalId),
      (annotations) => (evalAnnotations.value = annotations),
    )
  }

  async function deleteEvalAnnotation(artifactId: string, datasetId: string, annotationId: string) {
    const provider = evalStore.getProvider

    if (!provider.deleteEvalAnnotation) {
      throw new Error('Delete annotation method is not available')
    }

    await provider.deleteEvalAnnotation(artifactId, annotationId)
    const index = evalAnnotations.value.findIndex((item) => item.id === annotationId)
    if (index !== -1) {
      evalAnnotations.value.splice(index, 1)
    }
    await evalStore.initDataset(datasetId)
  }

  async function getEvalsDatasetAnnotationsSummary(datasetId: string) {
    await readLatest(
      'evalsDatasetSummary:' + datasetId,
      () => evalStore.getProvider.getEvalsDatasetAnnotationsSummary(datasetId),
      (summary) => (evalsAnnotationsSummaryByDatasetId.value[datasetId] = summary),
    )
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
    await traceStore.getNextPage(true)
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
    await traceStore.getNextPage(true)
  }

  async function getSpanAnnotations(artifactId: string, traceId: string, spanId: string) {
    await readLatest(
      'spanAnnotations',
      () => evalStore.getProvider.getSpanAnnotations(artifactId, traceId, spanId),
      (annotations) => (spanAnnotations.value = annotations),
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
    await traceStore.getNextPage(true)
  }

  async function getTracesAnnotationSummary(artifactId: string) {
    await readLatest(
      'tracesSummary',
      () => evalStore.getProvider.getTracesAnnotationSummary(artifactId),
      (summary) => (tracesAnnotationsSummary.value = summary),
    )
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
    evalsAnnotationsSummaryByDatasetId,
    tracesAnnotationsSummary,
  }
})
