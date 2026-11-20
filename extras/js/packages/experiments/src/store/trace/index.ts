import type { Trace } from '@/providers/ExperimentSnapshotApiProvider.interface'
import type { GetTracesParams, TypedColumnInfo, TypedTracesColumns } from '@/interfaces/interfaces'
import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import { INITIAL_REQUEST_PARAMS } from './trace.data'
import { useEvalsStore } from '../evals'
import { useDebounceFn } from '@vueuse/core'
import { useAnnotationsStore } from '../annotations'
import { useToast } from 'primevue'
import { showReadErrorToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'

export const useTraceStore = defineStore('trace', () => {
  const evalsStore = useEvalsStore()
  const annotationsStore = useAnnotationsStore()
  const toast = useToast()

  const requestParams = ref<GetTracesParams>({ ...INITIAL_REQUEST_PARAMS })
  const traces = ref<Trace[]>([])
  const loading = ref(false)
  const artifactId = ref<string | null>(null)
  const typedColumns = ref<TypedTracesColumns | null>(null)
  let typedColumnsRequest: Promise<void> | null = null

  const typedColumnsList = computed<TypedColumnInfo[]>(() => {
    if (!typedColumns.value) return []
    const entries = Object.entries(typedColumns.value)
    const formattedEntries = entries.map(([key, list]) => {
      return list.map((item) => ({ name: key + '.' + item.name, type: item.type }))
    })
    return formattedEntries.flat()
  })

  // Bumped when the list is reset or moved to another experiment. The store outlives its
  // view and Flow does not cancel reads, so an answer to an older read must be dropped.
  let listVersion = 0
  let reloadPending = false
  // The parameters the listed rows were read with. Until the reload for new parameters ends,
  // a next page would continue the old list's cursor with the new parameters.
  let listedParamsJson: string | null = null
  // Lets the view tell a reload that failed from one that did not run yet.
  let failedReloads = 0

  function isListCurrent() {
    return listedParamsJson === JSON.stringify(requestParams.value)
  }

  function getFailedReloads() {
    return failedReloads
  }

  function isCurrentRead(version: number, paramsJson?: string) {
    if (version !== listVersion) return false
    return paramsJson === undefined || paramsJson === JSON.stringify(requestParams.value)
  }

  async function getNextPage(reset: boolean = false) {
    const version = listVersion
    const paramsJson = JSON.stringify(requestParams.value)
    const params = JSON.parse(paramsJson)
    // The reset moves the provider's cursor back: until it ends, no listed rows continue it.
    if (reset) listedParamsJson = null
    // Both are posted at once, in order. A failed reset fails the read too, whose rows would
    // continue from the old cursor.
    const resetting = reset ? evalsStore.getProvider.resetTracesRequestParams() : undefined
    const [, data] = await Promise.all([resetting, evalsStore.getProvider.getTraces(params)])
    // Rows for older parameters: the reload for the current ones follows.
    if (!isCurrentRead(version, paramsJson)) return
    if (reset) {
      traces.value = []
      listedParamsJson = paramsJson
    }
    traces.value = [...traces.value, ...data]
    if (reset && artifactId.value) {
      await annotationsStore.getTracesAnnotationSummary(artifactId.value)
    }
  }

  function setRequestParams(params: Partial<GetTracesParams>) {
    requestParams.value = { ...requestParams.value, ...params }
  }

  function setLoading(value: boolean) {
    loading.value = value
  }

  function setArtifactId(id: string) {
    if (artifactId.value !== id) {
      listVersion++
      resetTypedColumns()
    }
    artifactId.value = id
  }

  function reset() {
    listVersion++
    reloadPending = false
    listedParamsJson = null
    requestParams.value = { ...INITIAL_REQUEST_PARAMS }
    if (evalsStore.hasProvider) {
      evalsStore.getProvider.resetTracesRequestParams().catch(() => undefined)
    }
    traces.value = []
    loading.value = false
    artifactId.value = null
    resetTypedColumns()
  }

  async function refresh() {
    evalsStore.clearSpanPayloads()
    if (loading.value) return
    const version = listVersion
    setLoading(true)
    try {
      const paramsJson = JSON.stringify(requestParams.value)
      const data = await evalsStore.getProvider.getFreshTraces(JSON.parse(paramsJson))
      if (!isCurrentRead(version, paramsJson)) return
      traces.value = [...data]
      if (artifactId.value) {
        await annotationsStore.getTracesAnnotationSummary(artifactId.value)
      }
    } catch (error) {
      showReadErrorToast(toast, error, getErrorMessage(error))
    } finally {
      // After a reset the loading flag belongs to the next experiment's view.
      if (isCurrentRead(version)) setLoading(false)
    }
  }

  async function reloadForParams() {
    // A reload scheduled before the view closed: its provider may be gone.
    if (!artifactId.value) return
    // Reads share the provider's page cursors, so they run one at a time.
    if (loading.value) {
      reloadPending = true
      return
    }
    const version = listVersion
    const paramsJson = JSON.stringify(requestParams.value)
    setLoading(true)
    try {
      await getNextPage(true)
    } catch (error) {
      // A failure for parameters changed since is not counted: their own reload follows.
      if (isCurrentRead(version, paramsJson)) failedReloads++
      showReadErrorToast(toast, error, getErrorMessage(error))
    } finally {
      if (isCurrentRead(version)) setLoading(false)
    }
  }

  const debouncedRequestParamsChange = useDebounceFn(reloadForParams, 500)

  /** Within the debounce window this merges with the reload already scheduled. */
  function scheduleReload() {
    debouncedRequestParamsChange()
  }

  watch(loading, (isLoading) => {
    if (isLoading || !reloadPending) return
    reloadPending = false
    reloadForParams()
  })

  /** Loaded once per artifact, when the filter editor first needs the keys. */
  function getTypedColumns(): Promise<void> {
    const id = artifactId.value
    if (!id) return Promise.resolve()
    if (!typedColumnsRequest) {
      const request = evalsStore.getProvider.getTracesColumns(id).then(
        (data) => {
          if (typedColumnsRequest === request) typedColumns.value = data
        },
        (error: unknown) => {
          if (typedColumnsRequest === request) typedColumnsRequest = null
          throw error
        },
      )
      typedColumnsRequest = request
    }
    return typedColumnsRequest
  }

  function resetTypedColumns() {
    typedColumnsRequest = null
    typedColumns.value = null
  }

  // reset() sets the parameters too; that is a close, not a change to reload for.
  watch(
    requestParams,
    () => {
      if (artifactId.value) debouncedRequestParamsChange()
    },
    { deep: true },
  )

  return {
    traces,
    requestParams,
    setRequestParams,
    loading,
    isListCurrent,
    getFailedReloads,
    scheduleReload,
    getNextPage,
    setLoading,
    reset,
    setArtifactId,
    refresh,
    getTypedColumns,
    typedColumns,
    typedColumnsList,
  }
})
