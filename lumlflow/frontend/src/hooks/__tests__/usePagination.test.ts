import { describe, expect, it, vi } from 'vitest'
import type { VirtualScrollerLazyEvent } from 'primevue'
import type { PaginatedResponse } from '@/api/api.interface'
import { usePagination } from '../usePagination'

interface Params {
  limit: number
  search?: string
  cursor?: string | null
}

function deferredPage() {
  let resolve!: (page: PaginatedResponse<string>) => void
  let reject!: (error: Error) => void
  const promise = new Promise<PaginatedResponse<string>>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

describe('usePagination', () => {
  it('appends pages using their cursors and stops at the last page', async () => {
    const method = vi
      .fn()
      .mockResolvedValueOnce({ items: ['first'], cursor: 'next' })
      .mockResolvedValueOnce({ items: ['second'], cursor: null })
    const pagination = usePagination<string, Params>(method, { limit: 1, search: 'query' })

    await pagination.getInitialPage()
    await pagination.getNextPage()
    await pagination.getNextPage()

    expect(pagination.data.value).toEqual(['first', 'second'])
    expect(method.mock.calls).toEqual([
      [{ limit: 1, search: 'query', cursor: null }],
      [{ limit: 1, search: 'query', cursor: 'next' }],
    ])
    expect(pagination.isLoading.value).toBe(false)
  })

  it('clears loading after a failed initial request and allows retry', async () => {
    const error = new Error('request failed')
    const method = vi
      .fn()
      .mockRejectedValueOnce(error)
      .mockResolvedValueOnce({ items: ['retry'], cursor: null })
    const pagination = usePagination<string, Params>(method)

    await expect(pagination.getInitialPage()).rejects.toBe(error)

    expect(pagination.isLoading.value).toBe(false)
    expect(pagination.data.value).toEqual([])
    await pagination.getInitialPage()
    expect(pagination.data.value).toEqual(['retry'])
  })

  it('clears loading when the method throws synchronously', async () => {
    const error = new Error('request failed')
    const pagination = usePagination<string, Params>(() => {
      throw error
    })

    await expect(pagination.getInitialPage()).rejects.toBe(error)

    expect(pagination.isLoading.value).toBe(false)
  })

  it('preserves the previous page and cursor on failure so lazy loading can retry', async () => {
    const error = new Error('request failed')
    const method = vi
      .fn()
      .mockResolvedValueOnce({ items: ['first'], cursor: 'next' })
      .mockRejectedValueOnce(error)
      .mockResolvedValueOnce({ items: ['retry'], cursor: null })
    const pagination = usePagination<string, Params>(method, { limit: 1 })
    const event = { last: 1 } as VirtualScrollerLazyEvent
    await pagination.getInitialPage()

    await expect(pagination.onLazyLoad(event)).rejects.toBe(error)

    expect(pagination.isLoading.value).toBe(false)
    expect(pagination.data.value).toEqual(['first'])
    await pagination.onLazyLoad(event)
    expect(pagination.data.value).toEqual(['first', 'retry'])
    expect(method.mock.calls[2]).toEqual([{ limit: 1, cursor: 'next' }])
  })

  it('discards a stale next page and cursor after the new search has loaded', async () => {
    const stalePage = deferredPage()
    const method = vi
      .fn()
      .mockResolvedValueOnce({ items: ['old'], cursor: 'old-next' })
      .mockReturnValueOnce(stalePage.promise)
      .mockResolvedValueOnce({ items: ['new'], cursor: 'new-next' })
      .mockResolvedValueOnce({ items: ['new-second'], cursor: null })
    const pagination = usePagination<string, Params>(method, { limit: 1, search: 'old' })
    await pagination.getInitialPage()
    const oldRequest = pagination.getNextPage()

    pagination.setParams({ limit: 1, search: 'new' })
    await pagination.getInitialPage()
    stalePage.resolve({ items: ['stale'], cursor: 'stale-next' })
    await oldRequest

    expect(pagination.data.value).toEqual(['new'])
    await pagination.getNextPage()
    expect(method.mock.calls[3]).toEqual([{ limit: 1, search: 'new', cursor: 'new-next' }])
    expect(pagination.data.value).toEqual(['new', 'new-second'])
  })

  it.each(['resolve', 'reject'] as const)(
    'keeps the new request loading when the stale next page %ss first',
    async (settlement) => {
      const stalePage = deferredPage()
      const newPage = deferredPage()
      const method = vi
        .fn()
        .mockResolvedValueOnce({ items: ['old'], cursor: 'old-next' })
        .mockReturnValueOnce(stalePage.promise)
        .mockReturnValueOnce(newPage.promise)
      const pagination = usePagination<string, Params>(method, { limit: 1, search: 'old' })
      await pagination.getInitialPage()
      const oldRequest = pagination.getNextPage()

      pagination.setParams({ limit: 1, search: 'new' })
      const newRequest = pagination.getInitialPage()
      if (settlement === 'reject') {
        const error = new Error('stale failure')
        const assertion = expect(oldRequest).rejects.toBe(error)
        stalePage.reject(error)
        await assertion
      } else {
        stalePage.resolve({ items: ['stale'], cursor: 'stale-next' })
        await oldRequest
      }

      expect(pagination.isLoading.value).toBe(true)
      expect(pagination.data.value).toEqual([])
      newPage.resolve({ items: ['new'], cursor: null })
      await newRequest
      expect(pagination.isLoading.value).toBe(false)
      expect(pagination.data.value).toEqual(['new'])
    },
  )

  it.each(['reset', 'setParams'] as const)(
    'invalidates an in-flight request on %s without requiring another request',
    async (action) => {
      const page = deferredPage()
      const method = vi.fn().mockReturnValue(page.promise)
      const pagination = usePagination<string, Params>(method)
      const request = pagination.getInitialPage()

      if (action === 'reset') pagination.reset()
      else pagination.setParams({ limit: 1, search: 'new' })
      page.resolve({ items: ['stale'], cursor: 'stale-next' })
      await request
      await pagination.getNextPage()

      expect(pagination.data.value).toEqual([])
      expect(pagination.isLoading.value).toBe(false)
      expect(method).toHaveBeenCalledTimes(1)
    },
  )

  it('keeps only the latest of overlapping initial requests', async () => {
    const firstPage = deferredPage()
    const secondPage = deferredPage()
    const method = vi
      .fn()
      .mockReturnValueOnce(firstPage.promise)
      .mockReturnValueOnce(secondPage.promise)
    const pagination = usePagination<string, Params>(method)
    const firstRequest = pagination.getInitialPage()
    const secondRequest = pagination.getInitialPage()
    secondPage.resolve({ items: ['latest'], cursor: null })
    await secondRequest
    firstPage.resolve({ items: ['stale'], cursor: 'stale-next' })
    await firstRequest

    expect(pagination.data.value).toEqual(['latest'])
    expect(pagination.isLoading.value).toBe(false)
  })

  it('does not request or append the same next page twice while it is loading', async () => {
    const nextPage = deferredPage()
    const method = vi
      .fn()
      .mockResolvedValueOnce({ items: ['first'], cursor: 'next' })
      .mockReturnValue(nextPage.promise)
    const pagination = usePagination<string, Params>(method, { limit: 1 })
    await pagination.getInitialPage()
    const nextRequest = pagination.getNextPage()
    const duplicateRequest = pagination.getNextPage()
    const lazyRequest = pagination.onLazyLoad({ last: 1 } as VirtualScrollerLazyEvent)

    expect(method).toHaveBeenCalledTimes(2)
    nextPage.resolve({ items: ['second'], cursor: null })
    await Promise.all([nextRequest, duplicateRequest, lazyRequest])
    expect(pagination.data.value).toEqual(['first', 'second'])
  })
})
