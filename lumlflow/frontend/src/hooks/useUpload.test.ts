import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '@/api/client'
import { useUpload } from './useUpload'

vi.mock('@/api/api.service', () => ({
  apiService: { uploadArtifact: vi.fn().mockResolvedValue({ job_id: 'job' }) },
}))
vi.mock('@/api/client', () => ({ api: { get: vi.fn() } }))
vi.mock('primevue', () => ({ useToast: () => ({ add: vi.fn() }) }))
vi.mock('@/toasts', () => ({ errorToast: vi.fn() }))

afterEach(() => {
  vi.useRealTimers()
})

describe('authenticated upload progress', () => {
  it('handles streamed events split across chunks through the API client', async () => {
    vi.useFakeTimers()
    const encoder = new TextEncoder()
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode('data: {"type":"progress","percent":50}\n'))
        controller.enqueue(encoder.encode('\ndata: {"type":"complete"}\n\n'))
        controller.close()
      },
    })
    vi.mocked(api.get).mockResolvedValue({ data: stream })
    const upload = useUpload()
    await upload.upload({} as Parameters<typeof upload.upload>[0])
    expect(api.get).toHaveBeenCalledWith('/luml/artifact/job/progress', {
      adapter: 'fetch',
      responseType: 'stream',
      signal: expect.any(AbortSignal),
    })
    expect(upload.progress.value).toBe(100)
    expect(upload.complete.value).toBe(true)
    expect(upload.loading.value).toBe(false)
    expect(upload.error.value).toBeNull()
  })

  it('reports an interrupted stream', async () => {
    const stream = new ReadableStream({
      start(controller) {
        controller.close()
      },
    })
    vi.mocked(api.get).mockResolvedValue({ data: stream })
    const upload = useUpload()
    await upload.upload({} as Parameters<typeof upload.upload>[0])
    expect(upload.error.value).toContain('Failed to receive upload progress')
    expect(upload.loading.value).toBe(false)
  })
})

it('cancels progress streaming when the component unmounts', async () => {
  const { defineComponent } = await import('vue')
  const { mount, flushPromises } = await import('@vue/test-utils')
  const cancel = vi.fn()
  const stream = new ReadableStream({ cancel })
  vi.mocked(api.get).mockResolvedValue({ data: stream })
  let upload!: ReturnType<typeof useUpload>
  const wrapper = mount(
    defineComponent({
      setup() {
        upload = useUpload()
        return () => null
      },
    }),
  )
  const request = upload.follow(async () => ({ job_id: 'job' }))
  await flushPromises()
  wrapper.unmount()
  await request
  expect(cancel).toHaveBeenCalledTimes(1)
  expect(upload.loading.value).toBe(false)
  expect(upload.error.value).toBeNull()
})

it('does not open a progress request when unmounted while starting an upload', async () => {
  const { defineComponent } = await import('vue')
  const { mount } = await import('@vue/test-utils')
  vi.mocked(api.get).mockClear()
  let upload!: ReturnType<typeof useUpload>
  let resolve!: (value: { job_id: string }) => void
  const started = new Promise<{ job_id: string }>((done) => {
    resolve = done
  })
  const wrapper = mount(
    defineComponent({
      setup() {
        upload = useUpload()
        return () => null
      },
    }),
  )
  const request = upload.follow(() => started)
  wrapper.unmount()
  resolve({ job_id: 'late' })
  await request
  expect(api.get).not.toHaveBeenCalled()
  expect(upload.loading.value).toBe(false)
})
