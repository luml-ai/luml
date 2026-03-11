import type {
  AddAnnotationPayload,
  Annotation,
  UpdateAnnotationPayload,
} from '@/components/annotations/annotations.interface'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { useEvalsStore } from './evals'

export const useAnnotationsStore = defineStore('annotations', () => {
  const evalStore = useEvalsStore()

  const isEditAvailable = ref(false)

  const addAnnotationData = ref<{ artifactId: string; datasetId: string; evalId: string } | null>(
    null,
  )

  const evalAnnotations = ref<Annotation[]>([])

  const isAddDialogVisible = computed(() => {
    return !!addAnnotationData.value
  })

  function allowEdit() {
    isEditAvailable.value = true
  }

  function disallowEdit() {
    isEditAvailable.value = false
  }

  function openAddDialog(artifactId: string, datasetId: string, evalId: string) {
    addAnnotationData.value = { artifactId, datasetId, evalId }
  }

  function closeAddDialog() {
    addAnnotationData.value = null
  }

  async function addEvalAnnotation(
    artifactId: string,
    datasetId: string,
    evalId: string,
    data: AddAnnotationPayload,
  ) {
    const provider = evalStore.getProvider

    if (!provider.createEvalAnnotation) {
      throw new Error('Create annotation method is not available')
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
  }
})
