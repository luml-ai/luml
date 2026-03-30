import type { SubsetInfo } from './datasets.interface'
import { defineStore } from 'pinia'
import { useArtifactsStore } from '../artifacts'
import { computed, ref, watch } from 'vue'
import {
  ArtifactTypeEnum,
  type Artifact,
  type DatasetManifest,
  type Split,
} from '@/lib/api/artifacts/interfaces'
import { ModelDownloader } from '@/lib/bucket-service'
import { ParquetHandler } from '@/utils/ParquetHandler'
import { from, fromCSV } from 'arquero'
import { getErrorMessage } from '@/helpers/helpers'
import { useToast } from 'primevue'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'

export const useDatasetsStore = defineStore('datasets', () => {
  const artifactsStore = useArtifactsStore()
  const toast = useToast()

  const isInitialized = ref(false)

  const loading = ref(false)

  const selectedSubset = ref<SubsetInfo | null>(null)

  const selectedSplit = ref<(Split & { name: string }) | null>(null)

  const downloader = ref<ModelDownloader | null>(null)

  const currentPage = ref<number | null>(null)

  const rowsPerPage = ref<number>(0)

  const tableColumns = ref<string[]>([])

  const tableRows = ref<Record<string, unknown>[]>([])

  const manifest = computed(() => {
    const isDataset = artifactsStore.currentArtifact?.type === ArtifactTypeEnum.dataset
    if (!artifactsStore.currentArtifact || !isDataset) return null
    return artifactsStore.currentArtifact.manifest as unknown as DatasetManifest
  })

  const payload = computed(() => {
    return manifest.value?.payload
  })

  const subsets = computed(() => {
    if (!payload.value) return []
    const subsets = payload.value.subsets

    const result: SubsetInfo[] = []

    for (const key in subsets) {
      const subset = subsets[key]
      const splits = subset.splits ? Object.entries(subset.splits) : []
      const numRows = splits.reduce((acc, [splitName, splitData]) => {
        acc += splitData.num_rows || 0
        return acc
      }, 0)
      result.push({
        name: key,
        subset,
        num_rows: numRows,
      })
    }

    return result
  })

  const splitsList = computed(() => {
    const splits = selectedSubset.value?.subset.splits
    if (!splits) return []
    const entries = Object.entries(splits)
    return entries.map(([name, split]) => ({
      name,
      ...split,
    }))
  })

  const chunks = computed(() => {
    return selectedSplit.value?.chunk_files || []
  })

  const datasetIndex = computed(() => {
    return artifactsStore.currentArtifact?.file_index || {}
  })

  const currentSplitFormat = computed(() => {
    return selectedSplit.value?.file_format
  })

  async function init() {
    const artifact = artifactsStore.currentArtifact
    if (!artifact) throw new Error('Current artifact does not exist')

    await setDownloader(artifact)
  }

  function setSelectedSubset(subsetName: string | null | undefined) {
    if (!subsetName) {
      selectedSubset.value = null
      return
    }
    const subset = subsets.value.find((subset) => subset.name === subsetName)
    if (!subset) {
      console.error(`Subset ${subsetName} not found`)
      selectedSubset.value = null
      return
    }
    selectedSubset.value = subset
  }

  function setSelectedSplit(splitName: string | null | undefined) {
    if (!splitName) {
      selectedSplit.value = null
      return
    }
    const split = selectedSubset.value?.subset.splits[splitName]
    if (!split) {
      console.error(`Split ${splitName} not found`)
      selectedSplit.value = null
      return
    }
    selectedSplit.value = {
      ...split,
      name: splitName,
    }
  }

  async function setDownloader(artifact: Artifact) {
    const url = await artifactsStore.getDownloadUrl(artifact.id)
    downloader.value = new ModelDownloader(url)
  }

  function setCurrentPage(page: number) {
    currentPage.value = page
  }

  async function getChunkData(page: number) {
    const chunk = chunks.value[page]
    if (!chunk) throw new Error('Chunk not found')
    const arrayBuffer = await downloader.value?.getFileFromBucket(datasetIndex.value, chunk, true)
    const { columns, rows } = await getDataFromBuffer(arrayBuffer)
    tableColumns.value = columns
    tableRows.value = rows
    if (!isInitialized.value) {
      isInitialized.value = true
    }
  }

  function getDataFromBuffer(
    arrayBuffer: ArrayBuffer,
  ): Promise<{ columns: string[]; rows: Record<string, unknown>[] }> {
    if (currentSplitFormat.value === 'parquet') {
      return getParquetData(arrayBuffer)
    }
    if (currentSplitFormat.value === 'csv') {
      return getCsvData(arrayBuffer)
    }
    throw new Error('Unsupported file format')
  }

  async function getParquetData(
    arrayBuffer: ArrayBuffer,
  ): Promise<{ columns: string[]; rows: Record<string, unknown>[] }> {
    const parquetHandler = new ParquetHandler(arrayBuffer)
    await parquetHandler.init()
    const data = await parquetHandler.read()
    const table = from(data)
    const columns = table.columnNames()
    return { columns, rows: data }
  }

  async function getCsvData(
    arrayBuffer: ArrayBuffer,
  ): Promise<{ columns: string[]; rows: Record<string, unknown>[] }> {
    const text = await new TextDecoder().decode(arrayBuffer)
    const table = fromCSV(text)
    const columns = table.columnNames()
    return { columns, rows: table.objects() as Record<string, unknown>[] }
  }

  function resetDataTable() {
    tableColumns.value = []
    tableRows.value = []
  }

  function reset() {
    selectedSubset.value = null
    selectedSplit.value = null
    currentPage.value = null
    isInitialized.value = false
    downloader.value = null
    rowsPerPage.value = 0
    loading.value = false
    resetDataTable()
  }

  function setRowsPerPage(count: number) {
    rowsPerPage.value = count
  }

  watch([currentPage, selectedSplit], async ([page]) => {
    if (page === null) {
      resetDataTable()
      return
    }

    try {
      if (isInitialized.value) {
        loading.value = true
      }
      await getChunkData(page)
      if (page === 0) {
        setRowsPerPage(tableRows.value.length)
      }
    } catch (e) {
      const message = getErrorMessage(e, 'Failed to get chunk data')
      toast.add(simpleErrorToast(message))
    } finally {
      loading.value = false
    }
  })

  return {
    manifest,
    selectedSubset,
    selectedSplit,
    subsets,
    splitsList,
    setSelectedSubset,
    setSelectedSplit,
    setCurrentPage,
    reset,
    tableColumns,
    tableRows,
    loading,
    rowsPerPage,
    init,
    isInitialized,
  }
})
