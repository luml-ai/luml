import type { MlModel } from '@/lib/api/orbit-ml-models/interfaces'
import { ModelDownloader } from '@/lib/bucket-service'
import { FnnxService } from '@/lib/fnnx/FnnxService'
import { ExperimentSnapshotWorkerProxy } from '@/modules/experiment-snapshot/providers/ExperimentSnapshotWorkerProxy'
import { useModelsStore } from '@/stores/models'
import { onUnmounted } from 'vue'

export const useExperimentSnapshotsDatabaseProvider = () => {
  const modelsStore = useModelsStore()

  let abortControllers: Record<string, AbortController> = {}

  const worker = new Worker(new URL('@/workers/experiment-snapshot', import.meta.url), {
    type: 'module',
  })

  worker.onerror = (e) => {
    console.error('❌ Worker error:', e)
  }

  worker.onmessageerror = (e) => {
    console.error('❌ Worker message error:', e)
  }

  function callWorker<T>(message: any): Promise<T> {
    const requestId = crypto.randomUUID()

    return new Promise((resolve, reject) => {
      const handler = (e: MessageEvent) => {
        if (e.data.requestId !== requestId) return
        worker.removeEventListener('message', handler)
        if (e.data.type === 'error') {
          reject(e.data.error)
        } else {
          resolve(e.data.data)
        }
      }
      worker.addEventListener('message', handler)
      worker.postMessage({ ...message, requestId })
    })
  }

  async function init(models: MlModel[]) {
    const payload = await Promise.all(
      models.map(async (model) => ({
        modelId: model.id,
        buffer: await loadArchiveBuffer(model),
      })),
    )

    await callWorker({
      type: 'init',
      payload,
    })

    const provider = new ExperimentSnapshotWorkerProxy(worker)
    modelsStore.setExperimentSnapshotProvider(provider)
  }

  async function loadArchiveBuffer(model: MlModel) {
    abortControllers[model.id]?.abort()
    abortControllers[model.id] = new AbortController()
    const { signal } = abortControllers[model.id]

    const archiveName = FnnxService.findExperimentSnapshotArchiveName(model.file_index)
    if (!archiveName)
      throw new Error(`Experiment snapshot data for model '${model.model_name}' was not found`)
    const url = await modelsStore.getDownloadUrl(model.id)
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
    Object.values(abortControllers).forEach((controller) => {
      controller.abort()
    })
  })

  return {
    init,
  }
}
