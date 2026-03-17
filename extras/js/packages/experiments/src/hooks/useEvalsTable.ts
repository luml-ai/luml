import type { AnnotationSummary } from '@/components/annotations/annotations.interface'
import type { SortParams } from '@/components/evals/evals.interface'
import type { ExpectationColumnData } from '@/components/table/ecpectation-column/interface'
import type { FeedbackColumnData } from '@/components/table/feedback-column/interface'
import type { EvalsInfo, GetEvalsByDatasetParams } from '@/interfaces/interfaces'
import type { DataTableSortEvent } from 'primevue'
import { computed, ref, type ComputedRef, type Ref } from 'vue'
import { useEvalsStore } from '@/store/evals'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { useToast } from 'primevue'
import { getErrorMessage } from '@/helpers/helpers'
import { downloadFileFromBlob } from '@/helpers/files'
import { from } from 'arquero'
import { valueToString } from '@/helpers/texts'

export const useEvalsTable = (
  evals: ComputedRef<EvalsInfo[]>,
  search: Readonly<Ref<string>>,
  datasetId: string,
  visibleColumns: Ref<string[]>,
) => {
  const evalsStore = useEvalsStore()
  const toast = useToast()

  const selectedColumns = ref<string[]>([])
  const sortParams = ref<SortParams>({
    sortField: 'created_at',
    sortOrder: 'desc',
  })
  const exportLoading = ref(false)

  const data = computed(() => getViewData(evals.value))

  function getViewData(evals: EvalsInfo[]) {
    return evals.map(getEvalInfo)
  }

  function getEvalInfo(item: EvalsInfo) {
    const feedbackObject = getFeedbackObject(item.annotations)
    const expectationObject = getExpectationObject(item.annotations)

    return {
      id: item.id,
      modelId: item.modelId,
      dataset_id: item.dataset_id,
      ...item.inputs,
      ...item.outputs,
      ...item.refs,
      ...item.scores,
      ...item.metadata,
      ...feedbackObject,
      ...expectationObject,
    }
  }

  function getFeedbackObject(summary: AnnotationSummary | null) {
    if (!summary) return {}
    return summary.feedback.reduce(
      (acc, item) => {
        acc[item.name] = {
          isFeedbackColumn: true,
          positiveCount: item.counts['true'] ?? 0,
          negativeCount: item.counts['false'] ?? 0,
        }
        return acc
      },
      {} as Record<string, FeedbackColumnData & { isFeedbackColumn: true }>,
    )
  }

  function getExpectationObject(summary: AnnotationSummary | null) {
    if (!summary) return {}
    return summary.expectations.reduce(
      (acc, item) => {
        acc[item.name] = {
          isExpectationColumn: true,
          total: item.total,
          positive: item.positive,
          negative: item.negative,
          value: item.value,
        }
        return acc
      },
      {} as Record<string, ExpectationColumnData & { isExpectationColumn: true }>,
    )
  }

  async function exportCSV() {
    const params = {
      dataset_id: datasetId,
      search: search.value,
      sort_by: sortParams.value.sortField,
      order: sortParams.value.sortOrder,
    }
    try {
      exportLoading.value = true
      const data = await evalsStore.getProvider.getAllDatasetEvals(params)
      const viewData = getViewData(data)
      const formattedData = viewData.map((item) => {
        const entries = Object.entries(item)
        const formattedEntries = entries
          .filter(([key]) => visibleColumns.value.includes(key))
          .map(([key, value]) => [key, valueToString(value)])
        return Object.fromEntries(formattedEntries)
      })
      const table = from(formattedData)
      const csv = table.toCSV()
      const blob = new Blob([csv], { type: 'text/csv' })
      downloadFileFromBlob(blob, `${datasetId}.csv`)
    } catch (error) {
      toast.add(simpleErrorToast(getErrorMessage(error, 'Failed to export CSV')))
    } finally {
      exportLoading.value = false
    }
  }

  function setSelectedColumns(columns: string[]) {
    selectedColumns.value = columns
  }

  function onSort(event: DataTableSortEvent) {
    const { sortField, sortOrder } = event
    sortParams.value = {
      sortField: sortField as GetEvalsByDatasetParams['sort_by'],
      sortOrder: sortOrder === 1 ? 'asc' : 'desc',
    }
  }

  return {
    exportCSV,
    setSelectedColumns,
    selectedColumns,
    data,
    sortParams,
    onSort,
    exportLoading,
  }
}
