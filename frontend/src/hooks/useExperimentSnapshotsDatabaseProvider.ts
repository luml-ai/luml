import type { ModelArtifact } from '@/lib/api/artifacts/interfaces'
import { ModelDownloader } from '@/lib/bucket-service'
import { FnnxService } from '@/lib/fnnx/FnnxService'
import { ExperimentSnapshotWorkerProxy } from '@luml/experiments'
import { useArtifactsStore } from '@/stores/artifacts'
import { onUnmounted, toRaw } from 'vue'

export const useExperimentSnapshotsDatabaseProvider = () => {
  const artifactsStore = useArtifactsStore()

  const abortControllers: Record<string, AbortController> = {}
  const initController = new AbortController()
  let unmounted = false
  let provider: ExperimentSnapshotWorkerProxy | null = null

  const worker = new Worker(new URL('@/workers/experiment-snapshot', import.meta.url), {
    type: 'module',
  })

  worker.onerror = (e) => {
    console.error('❌ Worker error:', e)
  }

  worker.onmessageerror = (e) => {
    console.error('❌ Worker message error:', e)
  }

  const workerProxy = new ExperimentSnapshotWorkerProxy(worker)

  async function init(models: ModelArtifact[]) {
    const payload = await Promise.all(
      models.map(async (model) => ({
        modelId: model.id,
        buffer: await loadArchiveBuffer(model),
      })),
    )

    if (unmounted) return
    await workerProxy.init(payload, initController.signal)

    if (unmounted) return
    provider = workerProxy
    artifactsStore.setExperimentSnapshotProvider(provider, terminateWorkerIfUnused)
  }

  function terminateWorkerIfUnused() {
    if (!unmounted) return
    if (provider && toRaw(artifactsStore.experimentSnapshotProvider) === provider) return
    worker.terminate()
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
    initController.abort()
    terminateWorkerIfUnused()
  })

  return {
    init,
  }
}
