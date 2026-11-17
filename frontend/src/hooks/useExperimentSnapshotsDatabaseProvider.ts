import type { ModelArtifact } from '@/lib/api/artifacts/interfaces'
import { ModelDownloader } from '@/lib/bucket-service'
import { toDownloadLocation } from '@/lib/bucket-service/presigned-url-cache'
import { FnnxService } from '@/lib/fnnx/FnnxService'
import {
  assertSourceHeaders,
  assertZipSnapshotFits,
  ExperimentSnapshotWorkerProxy,
  redactSecrets,
  toExperimentReadError,
  type ExperimentSnapshotModelSource,
} from '@luml/experiments'
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
    console.error('❌ Worker error:', redactSecrets(e.message ?? ''))
  }

  worker.onmessageerror = () => {
    console.error('❌ Worker message error')
  }

  const workerProxy = new ExperimentSnapshotWorkerProxy(worker, {
    sourceUrls: {
      get: (modelId) => artifactsStore.downloadUrlSource(modelId).getLocation(),
      renew: (modelId, failed) => artifactsStore.downloadUrlSource(modelId).renewLocation(failed),
    },
  })

  /**
   * A download error (axios) carries the presigned URL and the request headers; callers log
   * what init throws, so it only ever throws the redacted message.
   */
  async function init(models: ModelArtifact[]) {
    try {
      await open(models)
    } catch (error) {
      const { name, message } = (error ?? {}) as { name?: unknown; message?: unknown }
      if (name === 'AbortError') throw error
      const safe = new Error(redactSecrets(typeof message === 'string' ? message : String(error)))
      safe.name = typeof name === 'string' && /^\w+$/.test(name) ? name : 'Error'
      throw safe
    }
  }

  async function open(models: ModelArtifact[]) {
    const payload = await Promise.all(
      models.map((model) => loadSnapshotSource(model).catch((error) => failedSource(model, error))),
    )

    if (unmounted) return
    await workerProxy.init(payload, initController.signal)

    if (unmounted) return
    provider = workerProxy
    artifactsStore.setExperimentSnapshotProvider(provider, terminateWorkerIfUnused)
  }

  /** One experiment that could not be fetched is shown as failed; the others still open. */
  function failedSource(model: ModelArtifact, error: unknown): ExperimentSnapshotModelSource {
    const { name } = (error ?? {}) as { name?: unknown }
    if (name === 'AbortError' || name === 'CanceledError') throw error
    return { modelId: model.id, error: toExperimentReadError(error) }
  }

  function terminateWorkerIfUnused() {
    if (!unmounted) return
    if (provider && toRaw(artifactsStore.experimentSnapshotProvider) === provider) return
    workerProxy.terminate()
  }

  /**
   * A zipped DB is downloaded whole, after its directory shows it fits in the browser; a raw
   * `exp.db` is read in the worker by Range requests.
   */
  async function loadSnapshotSource(model: ModelArtifact): Promise<ExperimentSnapshotModelSource> {
    abortControllers[model.id]?.abort()
    abortControllers[model.id] = new AbortController()
    const { signal } = abortControllers[model.id]

    const memberName = FnnxService.findExperimentSnapshotArchiveName(model.file_index)
    if (!memberName)
      throw new Error(`Experiment snapshot data for model '${model.name}' was not found`)
    const urls = artifactsStore.downloadUrlSource(model.id)
    const location = toDownloadLocation(await urls.getLocation())
    assertSourceHeaders(location.headers)
    if (signal.aborted) throw new DOMException('Download aborted', 'AbortError')
    const [offset, size] = model.file_index[memberName]
    if (!memberName.endsWith('.zip')) {
      return { modelId: model.id, source: { kind: 'range', ...location, offset, size } }
    }
    await assertZipSnapshotFits(model.id, location, offset, size, signal)
    const buffer = await new ModelDownloader(urls).getFileFromBucket<ArrayBuffer>(
      model.file_index,
      memberName,
      true,
      0,
      signal,
    )
    return { modelId: model.id, source: { kind: 'zip', buffer } }
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
