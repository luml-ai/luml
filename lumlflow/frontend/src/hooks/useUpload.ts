import type { UploadArtifactPayload } from '@/components/upload/upload.interface'
import { apiService } from '@/api/api.service'
import { API_BASE_URL } from '@/api/client'
import { errorToast } from '@/toasts'
import { useToast } from 'primevue'
import { ref } from 'vue'

export const useUpload = () => {
  const toast = useToast()

  const progress = ref<number | null>(null)
  const error = ref<string | null>(null)
  const complete = ref<boolean>(false)
  const loading = ref<boolean>(false)

  async function upload(payload: UploadArtifactPayload) {
    await follow(() => apiService.uploadArtifact(payload))
  }

  /**
   * Any upload the daemon runs as a job: `start` asks for one, and the
   * progress stream it answers with is followed the same way whether the
   * job came from an experiment or from a flow cell's model.
   */
  async function follow(start: () => Promise<{ job_id: string }>) {
    try {
      loading.value = true
      error.value = null
      const response = await start()
      initProgressWatch(response.job_id)
    } catch (err) {
      loading.value = false
      toast.add(errorToast(err))
    }
  }

  function reset() {
    progress.value = null
    error.value = null
    complete.value = false
  }

  function initProgressWatch(jobId: string) {
    reset()
    const eventSource = new EventSource(`${API_BASE_URL}/luml/artifact/${jobId}/progress`)
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'progress') {
        progress.value = data.percent
      } else if (data.type === 'complete') {
        if (progress.value) {
          progress.value = 100
        }
        complete.value = true
        loading.value = false
        eventSource.close()
        setTimeout(() => {
          reset()
        }, 3000)
      } else if (data.type === 'error') {
        error.value = data.message
        loading.value = false
        eventSource.close()
      } else if (data.type === 'not_found') {
        error.value = 'Upload not found. Please try again.'
        loading.value = false
        eventSource.close()
      }
    }
    eventSource.onerror = () => {
      eventSource.close()
      if (!complete.value) {
        error.value = error.value ?? 'Failed to receive upload progress. Please try again.'
        loading.value = false
      }
    }
  }

  return { progress, error, upload, follow, complete, loading }
}
