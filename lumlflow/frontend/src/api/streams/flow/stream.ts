import { LogRing } from './logs'
import type { LogFrame, StreamFrame } from './types'

export const STREAM_PATH = '/api/flow/stream'

export const WS_UNAUTHORIZED = 4401

export type StreamStatus = 'connecting' | 'open' | 'dropped' | 'refused' | 'closed'

const BACKOFF_BASE_MS = 250
const BACKOFF_CAP_MS = 8000

export interface SocketLike {
  send(data: string): void
  close(): void
  onopen: (() => void) | null
  onmessage: ((event: { data: unknown }) => void) | null
  onclose: ((event: { code: number }) => void) | null
  onerror: ((event: unknown) => void) | null
}

export interface FlowStreamOptions {
  token: string
  baseUrl?: string
  open?: (url: string) => SocketLike
  schedule?: (run: () => void, afterMs: number) => void
}

export class FlowStream {
  readonly logs = new LogRing()

  private readonly options: FlowStreamOptions
  private readonly frameListeners = new Set<(frame: StreamFrame) => void>()
  private readonly statusListeners = new Set<(status: StreamStatus) => void>()
  private readonly journals = new Set<string>()
  private readonly journalFlowIds = new Map<string, string>()
  private readonly runs = new Set<string>()
  private readonly cursors = new Map<string, number>()
  private socket: SocketLike | null = null
  private ready = false
  private attempt = 0
  private stopped = false

  constructor(options: FlowStreamOptions) {
    this.options = options
  }

  onFrame(handler: (frame: StreamFrame) => void): () => void {
    this.frameListeners.add(handler)
    return () => this.frameListeners.delete(handler)
  }

  onStatus(handler: (status: StreamStatus) => void): () => void {
    this.statusListeners.add(handler)
    return () => this.statusListeners.delete(handler)
  }

  cursor(flow: string): number {
    return this.cursors.get(flow) ?? 0
  }

  connect(): void {
    if (this.socket !== null || this.stopped) return
    this.announce('connecting')
    const url = `${this.options.baseUrl ?? ''}${STREAM_PATH}?token=${encodeURIComponent(this.options.token)}`
    const socket = (this.options.open ?? defaultOpen)(url)
    this.socket = socket
    this.ready = false
    socket.onopen = () => {
      this.attempt = 0
      this.ready = true
      this.announce('open')
      this.resubscribe()
    }
    socket.onmessage = (event) => this.receive(event.data)
    socket.onclose = (event) => this.ended(socket, event.code)
    socket.onerror = () => {}
  }

  watchJournal(flow: string, flowId: string): void {
    const previous = this.journalFlowIds.get(flow)
    if (previous !== undefined && previous !== flowId) this.cursors.set(flow, 0)
    this.journalFlowIds.set(flow, flowId)
    this.journals.add(flow)
    this.send({ subscribe: 'journal', flow, cursor: this.cursor(flow) })
  }

  watchRun(flow: string, runId: string): void {
    this.runs.add(runKey(flow, runId))
    this.send({ subscribe: 'logs', flow, run_id: runId })
  }

  unwatchRun(flow: string, runId: string): void {
    this.runs.delete(runKey(flow, runId))
  }

  close(): void {
    this.stopped = true
    this.ready = false
    const socket = this.socket
    this.socket = null
    socket?.close()
    this.announce('closed')
  }

  private resubscribe(): void {
    for (const flow of this.journals) {
      this.send({ subscribe: 'journal', flow, cursor: this.cursor(flow) })
    }
    for (const key of this.runs) {
      const [flow, runId] = splitRunKey(key)
      this.send({ subscribe: 'logs', flow, run_id: runId })
    }
  }

  private send(message: Record<string, unknown>): void {
    if (!this.ready) return
    this.socket?.send(JSON.stringify(message))
  }

  private receive(data: unknown): void {
    if (typeof data !== 'string') return
    let frame: StreamFrame
    try {
      frame = JSON.parse(data) as StreamFrame
    } catch {
      return
    }
    if ('channel' in frame && frame.channel === 'journal') {
      if (frame.type === 'lagged') {
        this.resubscribe()
        this.deliver(frame)
        return
      }
      if (frame.type === 'state') {
        this.deliver(frame)
        return
      }
      this.cursors.set(frame.flow, Math.max(this.cursor(frame.flow), frame.step))
    } else if ('channel' in frame && frame.channel === 'logs') {
      if (!this.logs.append(frame)) return
    }
    this.deliver(frame)
  }

  private ended(socket: SocketLike, code: number): void {
    if (socket !== this.socket) return
    this.socket = null
    this.ready = false
    if (this.stopped) return
    if (code === WS_UNAUTHORIZED) {
      this.stopped = true
      this.announce('refused')
      return
    }
    this.announce('dropped')
    const wait = Math.min(BACKOFF_CAP_MS, BACKOFF_BASE_MS * 2 ** this.attempt)
    this.attempt += 1
    ;(this.options.schedule ?? defaultSchedule)(() => this.connect(), wait)
  }

  tail(flow: string, runId: string): LogFrame[] {
    return this.logs.tail(flow, runId)
  }

  private deliver(frame: StreamFrame): void {
    for (const handler of [...this.frameListeners]) handler(frame)
  }

  private announce(status: StreamStatus): void {
    for (const handler of [...this.statusListeners]) handler(status)
  }
}

function runKey(flow: string, runId: string): string {
  return `${flow}\n${runId}`
}

function splitRunKey(key: string): [string, string] {
  const [flow, runId] = key.split('\n')
  return [flow, runId ?? '']
}

function defaultOpen(url: string): SocketLike {
  const origin = window.location.origin.replace(/^http/, 'ws')
  return new WebSocket(url.startsWith('ws') ? url : `${origin}${url}`) as unknown as SocketLike
}

function defaultSchedule(run: () => void, afterMs: number): void {
  window.setTimeout(run, afterMs)
}
