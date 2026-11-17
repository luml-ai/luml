export type ReadRange = (offset: number, length: number) => Uint8Array

export interface RangeCacheOptions {
  chunkSize: number
  maxReadAheadBytes: number
  maxCacheBytes: number
}

export interface RangeReadStats {
  requests: number
  bytesFetched: number
  cacheHits: number
  cacheMisses: number
}

const SNAPSHOT_PAGE_SIZE = 16 * 1024
// An index lookup interleaves index and table pages, so a few scans are tracked at once.
const TRACKED_STREAMS = 4

interface ReadStream {
  lastChunk: number
  readAheadChunks: number
}

export const DEFAULT_RANGE_CACHE_OPTIONS: RangeCacheOptions = {
  chunkSize: 4 * SNAPSHOT_PAGE_SIZE,
  maxReadAheadBytes: 4 * 1024 * 1024,
  maxCacheBytes: 64 * 1024 * 1024,
}

/**
 * Serves byte reads from fixed, aligned chunks fetched through `readRange`. A miss fetches the
 * missing chunks in one request; sequential misses within a tracked stream double that stream's
 * read-ahead up to a cap, so a scan turns into a few large reads. Chunks are evicted least recently used beyond `maxCacheBytes`.
 */
export class RangeChunkCache {
  readonly stats: RangeReadStats = { requests: 0, bytesFetched: 0, cacheHits: 0, cacheMisses: 0 }
  private readonly options: RangeCacheOptions
  private readonly chunks = new Map<number, Uint8Array>()
  private cachedBytes = 0
  private streams: ReadStream[] = []
  private currentStream: ReadStream | null = null
  private readAheadChunks = 0

  constructor(
    private readonly readRange: ReadRange,
    readonly size: number,
    options: Partial<RangeCacheOptions> = {},
  ) {
    this.options = { ...DEFAULT_RANGE_CACHE_OPTIONS, ...options }
    const { chunkSize } = this.options
    if (chunkSize <= 0 || chunkSize % SNAPSHOT_PAGE_SIZE !== 0) {
      throw new RangeError(`chunkSize must be a positive multiple of ${SNAPSHOT_PAGE_SIZE}`)
    }
  }

  get cachedChunkCount(): number {
    return this.chunks.size
  }

  /** Caches the whole chunks of `head`, bytes from offset 0 fetched some other way. */
  seed(head: Uint8Array): void {
    const { chunkSize } = this.options
    for (let index = 0; index * chunkSize < head.length; index++) {
      const end = Math.min((index + 1) * chunkSize, this.size)
      if (head.length < end || this.chunks.has(index)) continue
      const chunk = head.slice(index * chunkSize, end)
      this.chunks.set(index, chunk)
      this.cachedBytes += chunk.length
    }
  }

  read(offset: number, length: number): Uint8Array {
    const end = Math.min(offset + length, this.size)
    if (offset < 0 || length < 0) throw new RangeError(`invalid read ${offset}+${length}`)
    if (offset >= end) return new Uint8Array(0)

    const { chunkSize } = this.options
    const firstChunk = Math.floor(offset / chunkSize)
    const lastChunk = Math.floor((end - 1) / chunkSize)
    this.updateReadAhead(firstChunk, lastChunk)
    this.ensureChunks(firstChunk, lastChunk)

    const result = new Uint8Array(end - offset)
    for (let index = firstChunk; index <= lastChunk; index++) {
      const chunk = this.chunks.get(index)!
      const chunkStart = index * chunkSize
      const from = Math.max(offset, chunkStart) - chunkStart
      const to = Math.min(end, chunkStart + chunk.length) - chunkStart
      result.set(chunk.subarray(from, to), chunkStart + from - offset)
    }
    this.evict()
    return result
  }

  private updateReadAhead(firstChunk: number, lastChunk: number): void {
    const index = this.streams.findIndex(
      (stream) => firstChunk === stream.lastChunk || firstChunk === stream.lastChunk + 1,
    )
    const stream = index === -1 ? { lastChunk, readAheadChunks: 0 } : this.streams[index]!
    if (index !== -1) this.streams.splice(index, 1)
    this.streams = [stream, ...this.streams].slice(0, TRACKED_STREAMS)
    stream.lastChunk = lastChunk
    if (index !== -1 && !this.chunks.has(firstChunk)) {
      const { chunkSize, maxReadAheadBytes } = this.options
      const maxChunks = Math.max(1, Math.floor(maxReadAheadBytes / chunkSize))
      stream.readAheadChunks = Math.min(maxChunks, Math.max(1, stream.readAheadChunks * 2))
    }
    this.readAheadChunks = stream.readAheadChunks
    this.currentStream = stream
  }

  private ensureChunks(firstChunk: number, lastChunk: number): void {
    let index = firstChunk
    while (index <= lastChunk) {
      const cached = this.chunks.get(index)
      if (cached) {
        this.stats.cacheHits++
        this.chunks.delete(index)
        this.chunks.set(index, cached)
        index++
        continue
      }
      index = this.fetchRun(index, lastChunk) + 1
    }
  }

  /** Fetches the missing run that starts at `start`; returns the last chunk index it covers. */
  private fetchRun(start: number, neededEnd: number): number {
    const { chunkSize } = this.options
    const finalChunk = Math.floor((this.size - 1) / chunkSize)
    const target = Math.min(finalChunk, Math.max(neededEnd, start + this.readAheadChunks))
    let runEnd = start
    while (runEnd < target && !this.chunks.has(runEnd + 1)) runEnd++
    // A one-chunk hole right after a cached chunk is fetched along: neighbouring B-tree pages
    // tend to be read together (opening reads chunks 0, 2, then 1), and one request is cheaper.
    const runStart =
      start >= 2 && !this.chunks.has(start - 1) && this.chunks.has(start - 2) ? start - 1 : start

    const byteStart = runStart * chunkSize
    const byteEnd = Math.min((runEnd + 1) * chunkSize, this.size)
    let data: Uint8Array
    try {
      data = this.readRange(byteStart, byteEnd - byteStart)
    } catch (error) {
      // A large read-ahead may be what failed (a timeout on a slow link): the retry starts a
      // new stream that asks only for what it needs and ramps up again.
      this.streams = this.streams.filter((stream) => stream !== this.currentStream)
      throw error
    }
    this.stats.requests++
    this.stats.bytesFetched += data.length
    if (data.length !== byteEnd - byteStart) {
      throw new RangeError(`short read at ${byteStart}: ${data.length} of ${byteEnd - byteStart}`)
    }
    for (let index = runStart; index <= runEnd; index++) {
      const from = (index - runStart) * chunkSize
      const chunk = data.slice(from, Math.min(from + chunkSize, data.length))
      this.chunks.set(index, chunk)
      this.cachedBytes += chunk.length
      if (index >= start && index <= neededEnd) this.stats.cacheMisses++
    }
    return Math.min(runEnd, neededEnd)
  }

  private evict(): void {
    for (const [index, chunk] of this.chunks) {
      if (this.cachedBytes <= this.options.maxCacheBytes) return
      this.chunks.delete(index)
      this.cachedBytes -= chunk.length
    }
  }
}
