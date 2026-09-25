import type { ModelArtifact } from '@/lib/api/artifacts/interfaces'
import { ModelDownloader } from '@/lib/bucket-service'
import { FnnxService } from '@/lib/fnnx/FnnxService'
import { ExperimentSnapshotWorkerProxy } from '@luml/experiments'
import { useArtifactsStore } from '@/stores/artifacts'
import { onUnmounted } from 'vue'

export const useExperimentSnapshotsDatabaseProvider = () => {
  const artifactsStore = useArtifactsStore()

  const abortControllers: Record<string, AbortController> = {}
  const pendingWorkerCalls = new Map<(e: MessageEvent) => void, (reason: Error) => void>()
  let unmounted = false

  const worker = new Worker(new URL('@/workers/experiment-snapshot', import.meta.url), {
    type: 'module',
  })

  worker.onerror = (e) => {
    console.error('❌ Worker error:', e)
  }

  worker.onmessageerror = (e) => {
    console.error('❌ Worker message error:', e)
  }

  function callWorker<T>(message: Record<string, unknown>): Promise<T> {
    if (unmounted) return Promise.reject(new Error('Experiment snapshot view was unmounted'))
    const requestId = crypto.randomUUID()

    return new Promise((resolve, reject) => {
      const handler = (e: MessageEvent) => {
        if (e.data.requestId !== requestId) return
        worker.removeEventListener('message', handler)
        pendingWorkerCalls.delete(handler)
        if (e.data.type === 'error') {
          reject(e.data.error)
        } else {
          resolve(e.data.data)
        }
      }
      worker.addEventListener('message', handler)
      pendingWorkerCalls.set(handler, reject)
      worker.postMessage({ ...message, requestId })
    })
  }

  async function init(models: ModelArtifact[]) {
    const payload = await Promise.all(
      models.map(async (model) => ({
        modelId: model.id,
        buffer: await loadArchiveBuffer(model),
      })),
    )

    if (unmounted) return
    await callWorker({
      type: 'init',
      payload,
    })

    if (unmounted) return
    const provider = new ExperimentSnapshotWorkerProxy(worker)
    artifactsStore.setExperimentSnapshotProvider(provider)
  }

  async function loadArchiveBuffer(model: ModelArtifact) {
    abortControllers[model.id]?.abort()
    abortControllers[model.id] = new AbortController()
    const { signal } = abortControllers[model.id]

    const archiveName = FnnxService.findExperimentSnapshotArchiveName(model.file_index)
    if (!archiveName)
      throw new Error(`Experiment snapshot data for model '${model.name}' was not found`)
    const url = await artifactsStore.getDownloadUrl(model.id)
    if (signal.aborted) throw new DOMException('Download aborted', 'AbortError')
    const modelDownloader = new ModelDownloader(url)
    return modelDownloader.getFileFromBucket<ArrayBuffer>(
      model.file_index,
      archiveName,
      true,
      0,
      signal,
    )
  }

  onUnmounted(() => {
    unmounted = true
    Object.values(abortControllers).forEach((controller) => {
      controller.abort()
    })
    pendingWorkerCalls.forEach((reject, handler) => {
      worker.removeEventListener('message', handler)
      reject(new Error('Experiment snapshot view was unmounted'))
    })
    pendingWorkerCalls.clear()
    worker.terminate()
  })

  return {
    init,
  }
}
