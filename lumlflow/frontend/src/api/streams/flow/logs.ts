import type { LogFrame } from './types'

export const RING_CHUNKS = 512
export const RUNS_KEPT = 8

interface RunTail {
  chunks: LogFrame[]
  highestSeq: number
  seen: boolean
}

export class LogRing {
  private readonly tails = new Map<string, RunTail>()

  constructor(
    private readonly chunks: number = RING_CHUNKS,
    private readonly runs: number = RUNS_KEPT,
  ) {}

  append(frame: LogFrame): boolean {
    const key = keyOf(frame.flow, frame.run_id)
    const tail = this.tails.get(key) ?? { chunks: [], highestSeq: 0, seen: false }
    if (tail.seen && frame.seq <= tail.highestSeq) return false
    tail.chunks.push(frame)
    tail.highestSeq = frame.seq
    tail.seen = true
    if (tail.chunks.length > this.chunks) tail.chunks.splice(0, tail.chunks.length - this.chunks)
    this.tails.delete(key)
    this.tails.set(key, tail)
    while (this.tails.size > this.runs) {
      const oldest = this.tails.keys().next()
      if (oldest.done) break
      this.tails.delete(oldest.value)
    }
    return true
  }

  tail(flow: string, runId: string): LogFrame[] {
    return [...(this.tails.get(keyOf(flow, runId))?.chunks ?? [])]
  }
}

function keyOf(flow: string, runId: string): string {
  return `${flow} ${runId}`
}
