export const PRESIGNED_URL_REUSE_MS = 30 * 60 * 1000
/** A URL younger than this is not renewed: storage that rejects every URL costs one renewal. */
export const PRESIGNED_URL_MIN_RENEW_AGE_MS = 30 * 1000

/**
 * Where an artifact is read from: a presigned URL, or a URL that also needs request headers
 * (a bearer token) or a credentials mode. Same shape as `SnapshotSourceLocation`.
 */
export interface DownloadLocation {
  url: string
  headers?: Readonly<Record<string, string>>
  credentials?: RequestCredentials
}

/** A bare URL, or a location with headers, exactly as the issuer returned it. */
export type DownloadRef = string | DownloadLocation

export interface DownloadUrlSource {
  get(): Promise<string>
  renew(failedUrl: string): Promise<string>
  withUrl<T>(request: (url: string) => Promise<T>): Promise<T>
  getLocation(): Promise<DownloadRef>
  renewLocation(failed: DownloadRef): Promise<DownloadRef>
  withLocation<T>(request: (location: DownloadLocation) => Promise<T>): Promise<T>
}

interface IssuedRef {
  ref: DownloadRef
  issuedAt: number
}

export function toDownloadLocation(ref: DownloadRef): DownloadLocation {
  return typeof ref === 'string' ? { url: ref } : ref
}

function headerEntries(location: DownloadLocation): string {
  return Object.entries(location.headers ?? {})
    .map(([name, value]) => `${name.toLowerCase()}:${value}`)
    .sort()
    .join('\n')
}

export function sameDownloadLocation(a: DownloadRef, b: DownloadRef): boolean {
  const left = toDownloadLocation(a)
  const right = toDownloadLocation(b)
  return (
    left.url === right.url &&
    (left.credentials ?? null) === (right.credentials ?? null) &&
    headerEntries(left) === headerEntries(right)
  )
}

function isAbort(error: unknown): boolean {
  const name = (error as { name?: unknown } | null)?.name
  return name === 'AbortError' || name === 'CanceledError'
}

/**
 * One download location per artifact, reused for 30 minutes. It is renewed early only when a
 * request with it fails and it is at least 30 seconds old, because some storage setups issue
 * URLs or tokens that expire sooner than the platform expects. Concurrent callers that need a
 * new one share one backend request.
 */
export class PresignedUrlCache {
  private readonly issued = new Map<string, IssuedRef>()
  private readonly pending = new Map<string, Promise<DownloadRef>>()

  constructor(
    private readonly fetchUrl: (artifactId: string) => Promise<DownloadRef>,
    private readonly reuseMs = PRESIGNED_URL_REUSE_MS,
    private readonly minRenewAgeMs = PRESIGNED_URL_MIN_RENEW_AGE_MS,
  ) {}

  async get(artifactId: string): Promise<string> {
    return toDownloadLocation(await this.getLocation(artifactId)).url
  }

  /** A request with `failedUrl` failed; a URL issued since then is returned instead of a new one. */
  async renew(artifactId: string, failedUrl: string): Promise<string> {
    const renewed = await this.renewUnless(
      artifactId,
      (ref) => toDownloadLocation(ref).url !== failedUrl,
    )
    return toDownloadLocation(renewed).url
  }

  getLocation(artifactId: string): Promise<DownloadRef> {
    const current = this.issued.get(artifactId)
    if (current && this.isFresh(current)) return Promise.resolve(current.ref)
    return this.issue(artifactId)
  }

  /** As `renew`, comparing headers too: a renewed token for the same URL counts as new. */
  renewLocation(artifactId: string, failed: DownloadRef): Promise<DownloadRef> {
    return this.renewUnless(artifactId, (ref) => !sameDownloadLocation(ref, failed))
  }

  /**
   * Runs `request` with the cached URL; on failure renews once and retries once. When the
   * renewal hands back the URL that just failed, the error surfaces without a retry.
   */
  withUrl<T>(artifactId: string, request: (url: string) => Promise<T>): Promise<T> {
    return this.withLocation(artifactId, (location) => request(location.url))
  }

  withLocation<T>(
    artifactId: string,
    request: (location: DownloadLocation) => Promise<T>,
  ): Promise<T> {
    return this.getLocation(artifactId).then(async (ref) => {
      try {
        return await request(toDownloadLocation(ref))
      } catch (error) {
        if (isAbort(error)) throw error
        const renewed = await this.renewLocation(artifactId, ref)
        if (sameDownloadLocation(renewed, ref)) throw error
        return request(toDownloadLocation(renewed))
      }
    })
  }

  source(artifactId: string): DownloadUrlSource {
    return {
      get: () => this.get(artifactId),
      renew: (failedUrl) => this.renew(artifactId, failedUrl),
      withUrl: (request) => this.withUrl(artifactId, request),
      getLocation: () => this.getLocation(artifactId),
      renewLocation: (failed) => this.renewLocation(artifactId, failed),
      withLocation: (request) => this.withLocation(artifactId, request),
    }
  }

  private renewUnless(
    artifactId: string,
    issuedSinceFailure: (ref: DownloadRef) => boolean,
  ): Promise<DownloadRef> {
    const current = this.issued.get(artifactId)
    if (
      current &&
      (this.isRecent(current) || (issuedSinceFailure(current.ref) && this.isFresh(current)))
    ) {
      return Promise.resolve(current.ref)
    }
    return this.issue(artifactId)
  }

  private isRecent(entry: IssuedRef): boolean {
    return Date.now() - entry.issuedAt < this.minRenewAgeMs
  }

  private isFresh(entry: IssuedRef): boolean {
    return Date.now() - entry.issuedAt < this.reuseMs
  }

  private issue(artifactId: string): Promise<DownloadRef> {
    const inFlight = this.pending.get(artifactId)
    if (inFlight) return inFlight
    const request = this.fetchUrl(artifactId)
      .then((ref) => {
        this.issued.set(artifactId, { ref, issuedAt: Date.now() })
        return ref
      })
      .finally(() => this.pending.delete(artifactId))
    this.pending.set(artifactId, request)
    return request
  }
}
