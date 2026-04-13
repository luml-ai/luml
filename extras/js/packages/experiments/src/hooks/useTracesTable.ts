import type { AnnotationSummary } from '@experiments/components/annotations/annotations.interface'
import type { ExpectationColumnData } from '@experiments/components/table/ecpectation-column/interface'
import type { FeedbackColumnData } from '@experiments/components/table/feedback-column/interface'
import type { Trace } from '@experiments/providers/ExperimentSnapshotApiProvider.interface'
import type { GetTracesParams } from '@experiments/interfaces/interfaces'
import { computed, ref, type Ref } from 'vue'
import { useEvalsStore } from '@experiments/store/evals'
import { simpleErrorToast } from '@experiments/lib/primevue/data/toasts'
import { useToast } from 'primevue'
import { formattedDate, getErrorMessage } from '@experiments/helpers/helpers'
import { downloadFileFromBlob } from '@experiments/helpers/files'
import { from } from 'arquero'
import { valueToString } from '@experiments/helpers/texts'

export const useTracesTable = (
  traces: Ref<Trace[]>,
  selectedColumns: Ref<string[]>,
  requestParams: Ref<GetTracesParams>,
) => {
  const evalsStore = useEvalsStore()
  const toast = useToast()

  const exportLoading = ref(false)

  const data = computed(() => getViewData(traces.value))

  function getViewData(traces: Trace[]) {
    return traces.map(getTraceInfo)
  }

  function getTraceInfo(item: Trace) {
    const feedbackObject = getFeedbackObject(item.annotations)
    const expectationObject = getExpectationObject(item.annotations)

    const result: Record<string, any> = {
      ...item,
      created_at: formattedDate(item.created_at),
      ...feedbackObject,
      ...expectationObject,
    }

    delete result.annotations

    return result
  }

  function getFeedbackObject(summary: AnnotationSummary | null) {
    if (!summary) return {}
    return summary.feedback.reduce(
      (acc, item) => {
        acc[item.name + ' (feedback)'] = {
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
        acc[item.name + ' (expectation)'] = {
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
      search: requestParams.value.search,
      sort_by: requestParams.value.sort_by,
      order: requestParams.value.order,
      filters: requestParams.value.filters,
    }
    try {
      exportLoading.value = true
      const data = await evalsStore.getProvider.getAllTraces(params)
      const viewData = getViewData(data)
      const formattedData = viewData.map((item) => {
        const entries = Object.entries(item)
        const formattedEntries = entries
          .filter(([key]) => selectedColumns.value.includes(key))
          .map(([key, value]) => [key, valueToString(value)])
        return Object.fromEntries(formattedEntries)
      })
      const table = from(formattedData)
      const csv = table.toCSV()
      const blob = new Blob([csv], { type: 'text/csv' })
      downloadFileFromBlob(blob, `traces.csv`)
    } catch (error) {
      toast.add(simpleErrorToast(getErrorMessage(error, 'Failed to export CSV')))
    } finally {
      exportLoading.value = false
    }
  }

  return {
    exportCSV,
    data,
    exportLoading,
  }
}
