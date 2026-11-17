import type { UploadArtifactPayload } from '@/components/upload/upload.interface'
import { apiService } from '@/api/api.service'
import { api } from '@/api/client'
import { errorToast } from '@/toasts'
import { useToast } from 'primevue'
import { getCurrentScope, onScopeDispose, ref } from 'vue'

export const useUpload = () => {
  const toast = useToast()
  const controller = new AbortController()
  const readers = new Set<ReadableStreamDefaultReader<Uint8Array>>()
  const resetTimers = new Set<ReturnType<typeof setTimeout>>()
  let disposed = false

  if (getCurrentScope()) {
    onScopeDispose(() => {
      disposed = true
      controller.abort()
      for (const reader of readers) void reader.cancel().catch(() => {})
      for (const timer of resetTimers) clearTimeout(timer)
      loading.value = false
    })
  }

  const progress = ref<number | null>(null)
  const error = ref<string | null>(null)
  const complete = ref<boolean>(false)
  const loading = ref<boolean>(false)

  async function upload(payload: UploadArtifactPayload) {
    await follow(() => apiService.uploadArtifact(payload))
  }

  async function follow(start: () => Promise<{ job_id: string }>) {
    if (disposed) return
    try {
      loading.value = true
      error.value = null
      const response = await start()
      if (!disposed) await initProgressWatch(response.job_id)
    } catch (err) {
      loading.value = false
      if (!disposed) toast.add(errorToast(err))
    }
  }

  function reset() {
    progress.value = null
    error.value = null
    complete.value = false
  }

  async function initProgressWatch(jobId: string) {
    reset()
    const { data: stream } = await api.get<ReadableStream<Uint8Array>>(
      `/luml/artifact/${jobId}/progress`,
      { adapter: 'fetch', responseType: 'stream', signal: controller.signal },
    )
    const reader = stream.getReader()
    if (disposed) {
      await reader.cancel()
      return
    }
    readers.add(reader)
    const decoder = new TextDecoder()
    let buffer = ''
    function handleEvent(event: string) {
      const data = JSON.parse(event.slice('data: '.length))
      if (data.type === 'progress') {
        progress.value = data.percent
      } else if (data.type === 'complete') {
        if (progress.value) {
          progress.value = 100
        }
        complete.value = true
        loading.value = false
        const timer = setTimeout(() => {
          resetTimers.delete(timer)
          reset()
        }, 3000)
        resetTimers.add(timer)
      } else if (data.type === 'error') {
        error.value = data.message
        loading.value = false
      } else if (data.type === 'not_found') {
        error.value = 'Upload not found. Please try again.'
        loading.value = false
      }
    }
    try {
      while (!disposed && !complete.value && !error.value) {
        const { value, done } = await reader.read()
        if (done || disposed) break
        buffer += decoder.decode(value, { stream: true })
        let boundary: number
        while ((boundary = buffer.indexOf('\n\n')) !== -1) {
          const event = buffer.slice(0, boundary)
          buffer = buffer.slice(boundary + 2)
          if (event.startsWith('data: ')) handleEvent(event)
        }
      }
    } finally {
      readers.delete(reader)
      await reader.cancel()
      if (!disposed && !complete.value) {
        error.value = error.value ?? 'Failed to receive upload progress. Please try again.'
        loading.value = false
      }
    }
  }

  return { progress, error, upload, follow, complete, loading }
}
