import type { PaginatedResponse } from '@/api/api.interface'
import type { VirtualScrollerLazyEvent } from 'primevue'
import { ref } from 'vue'

const DEFAULT_LIMIT = 20

export const usePagination = <T, P extends object>(
  method: (params: P) => Promise<PaginatedResponse<T>>,
  initialParams: P = { limit: DEFAULT_LIMIT } as P,
) => {
  const params = ref<P>(initialParams)
  const cursors = ref<Array<string | null>>([])
  const data = ref<T[]>([])
  const isLoading = ref(false)

  function setParams(value: Partial<P>) {
    params.value = value
  }

  function getParams() {
    return params.value
  }

  function getNextPageCursor() {
    return cursors.value[cursors.value.length - 1] ?? null
  }

  async function getInitialPage() {
    reset()
    await loadData(null)
  }

  async function getNextPage() {
    const cursor = getNextPageCursor()
    if (!cursor) return
    await loadData(cursor)
  }

  async function loadData(cursor: string | null) {
    isLoading.value = true
    const response = await method({ ...getParams(), cursor })
    const currentData = data.value as T[]
    data.value = [...currentData, ...response.items]
    cursors.value.push(response.cursor)
    isLoading.value = false
  }

  function reset() {
    if (data.value.length) {
      data.value = []
    }

    if (cursors.value.length) {
      cursors.value = []
    }

    if (isLoading.value) {
      isLoading.value = false
    }
  }

  async function onLazyLoad(event: VirtualScrollerLazyEvent) {
    if (isLoading.value) return
    const { last } = event
    const pageIndex = cursors.value.length
    if (last === pageIndex * getParams().limit) {
      await getNextPage()
    }
  }

  return {
    data,
    setParams,
    getParams,
    getNextPage,
    getInitialPage,
    reset,
    onLazyLoad,
    isLoading,
  }
}
