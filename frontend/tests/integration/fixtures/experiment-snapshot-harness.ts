// Browser harness for experiment-snapshot-range.spec.ts: the real worker proxy and presigned
// URL cache on the main thread, talking to the real experiment snapshot worker.
import {
  assertZipSnapshotFits,
  ExperimentSnapshotWorkerProxy,
  MetricBucketStore,
  toExperimentReadError,
} from '@luml/experiments'
import {
  PRESIGNED_URL_REUSE_MS,
  PresignedUrlCache,
  toDownloadLocation,
  type DownloadRef,
} from '../../../src/lib/bucket-service/presigned-url-cache'

interface HarnessSource {
  modelId: string
  artifact: string
  /** A storage profile of the spec's server; without one, the plain `/sign` store. */
  profile?: string
  kind: 'range' | 'zip'
  offset: number
  size: number
}

function describeError(error: unknown) {
  if (typeof error === 'string') return { message: error }
  const { name, message, code, modelId } = error as Record<string, unknown>
  return { name, message, code, modelId }
}

async function settle<T>(work: Promise<T>) {
  try {
    return { ok: true, value: await work }
  } catch (error) {
    return { ok: false, error: describeError(error) }
  }
}

/** A profile's locations are JSON (a URL or a URL with headers); the plain store's are text. */
async function issue(key: string): Promise<DownloadRef> {
  const [profile, artifact] = key.includes('|') ? key.split('|') : [null, key]
  if (!profile) {
    const response = await fetch(`/sign?artifact=${encodeURIComponent(key)}`)
    return response.text()
  }
  const query = `profile=${encodeURIComponent(profile)}&artifact=${encodeURIComponent(artifact ?? '')}`
  const response = await fetch(`/sign-profile?${query}`)
  return (await response.json()) as DownloadRef
}

export function installHarness(worker: Worker): void {
  // The specs expire URLs seconds after issue, so the minimum age before a renewal is off.
  const urls = new PresignedUrlCache(issue, PRESIGNED_URL_REUSE_MS, 0)
  // Every message the worker posted, to check that none of them carries a credential.
  const posted: string[] = []
  worker.addEventListener('message', (event) => posted.push(JSON.stringify(event.data)))
  const keyOf = new Map<string, string>()
  const urlKey = (modelId: string) => keyOf.get(modelId) ?? modelId
  const proxy = new ExperimentSnapshotWorkerProxy(worker, {
    sourceUrls: {
      get: (modelId) => urls.getLocation(urlKey(modelId)),
      renew: (modelId, failed) => urls.renewLocation(urlKey(modelId), failed),
    },
  })

  Object.assign(window, {
    harness: {
      async init(sources: HarnessSource[]) {
        const modelsInfo = await Promise.all(
          sources.map(async ({ modelId, artifact, profile, kind, offset, size }) => {
            const key = profile ? `${profile}|${artifact}` : artifact
            keyOf.set(modelId, key)
            const location = toDownloadLocation(await urls.getLocation(key))
            if (kind === 'range') {
              return { modelId, source: { kind: 'range' as const, ...location, offset, size } }
            }
            // A zipped snapshot is checked by its directory and downloaded whole on the main
            // thread, as the app does.
            try {
              await assertZipSnapshotFits(modelId, location, offset, size)
            } catch (error) {
              return { modelId, error: toExperimentReadError(error) }
            }
            const response = await fetch(location.url, {
              headers: { ...location.headers, Range: `bytes=${offset}-${offset + size - 1}` },
            })
            return {
              modelId,
              source: { kind: 'zip' as const, buffer: await response.arrayBuffer() },
            }
          }),
        )
        return settle(proxy.init(modelsInfo))
      },
      call(method: string, args: unknown[] = []) {
        const target = proxy as unknown as Record<
          string,
          (...values: unknown[]) => Promise<unknown>
        >
        const fn = target[method]
        if (!fn) return settle(Promise.reject(new Error(`no method ${method}`)))
        return settle(fn.apply(proxy, args))
      },
      stats() {
        return settle(proxy.getTransportStats())
      },
      posted() {
        return posted
      },
      /**
       * One chart's settled state through the real store: the plan's level and the series it
       * drew, how many provider bucket calls it made at which levels, and the store's statuses
       * afterwards (bucket answers can add to them).
       */
      async chartState(request: {
        modelIds: string[]
        keys: string[]
        bucketBudget: number
        startStep?: number
        endStep?: number
      }) {
        const levels: number[] = []
        const counting = new Proxy(proxy, {
          get(target, property, receiver) {
            const value = Reflect.get(target, property, receiver)
            if (property !== 'getMetricBuckets' || typeof value !== 'function') {
              return typeof value === 'function' ? value.bind(target) : value
            }
            return (bucketRequest: { level: number }, signal?: AbortSignal) => {
              levels.push(bucketRequest.level)
              return value.call(target, bucketRequest, signal)
            }
          },
        })
        const store = new MetricBucketStore(counting, { debounceMs: 0, requestTimeoutMs: 20_000 })
        try {
          const drawn = new Promise<Record<string, unknown>>((resolve, reject) => {
            const timer = setTimeout(() => reject(new Error('chart did not settle')), 20_000)
            const chart = store.subscribe((state) => {
              if (!state.plan || state.loading) return
              clearTimeout(timer)
              resolve({
                level: state.plan.level,
                fetchLevels: [...levels],
                errors: state.errors,
                series: state.series.map(({ modelId, key, level, final, buckets }) => ({
                  modelId,
                  key,
                  level,
                  final,
                  buckets,
                })),
              })
            })
            chart.request(request)
          })
          return await settle(
            drawn.then(async (state) => {
              const { statuses } = await store.loadCatalogs()
              return { ...state, statuses }
            }),
          )
        } finally {
          store.dispose()
        }
      },
      /** The error messages a chart of `key` over every open model shows, after a reload. */
      async chartErrors(key: string): Promise<string[]> {
        const store = new MetricBucketStore(proxy, { debounceMs: 0, requestTimeoutMs: 10_000 })
        try {
          const catalogs = await store.loadCatalogs()
          await store.reload([...catalogs.catalogs.keys(), ...catalogs.errors.keys()])
          const modelIds = [...catalogs.catalogs.keys(), ...catalogs.errors.keys()]
          const messages: string[] = []
          await new Promise<void>((resolve) => {
            const chart = store.subscribe((state) => {
              messages.push(...state.errors.map((item) => item.error.message))
              if (state.plan !== null && !state.loading) resolve()
              if (state.errors.length && !state.loading) resolve()
            })
            chart.request({ modelIds, keys: [key], bucketBudget: 100 })
            setTimeout(resolve, 5000)
          })
          return messages
        } catch (error) {
          return [describeError(error).message as string]
        } finally {
          store.dispose()
        }
      },
    },
  })
}
