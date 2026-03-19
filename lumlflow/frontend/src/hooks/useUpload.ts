import type { UploadArtifactPayload } from '@/components/upload/upload.interface'
import { apiService } from '@/api/api.service'
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
    try {
      loading.value = true
      const response = await apiService.uploadArtifact(payload)
      initProgressWatch(response.job_id)
    } catch (error) {
      toast.add(errorToast(error))
    }
  }

  function reset() {
    progress.value = null
    error.value = null
    complete.value = false
  }

  function initProgressWatch(jobId: string) {
    reset()
    const eventSource = new EventSource(
      `${import.meta.env.VITE_API_URL}/luml/artifact/${jobId}/progress`,
    )
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
        setTimeout(() => {
          reset()
        }, 3000)
      } else if (data.type === 'error') {
        error.value = data.message
        loading.value = false
      }
    }
    eventSource.onerror = () => {
      eventSource.close()
    }
  }

  return { progress, error, upload, complete, loading }
}
