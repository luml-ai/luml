/**
 * The socket the workbench watches a workspace through — both channels, one
 * connection, one frame order.
 *
 * The whole point of it is that a reconnect is a latency event and never a
 * data one. Every journal frame carries the flow-global `step`; this holds the
 * highest it has seen per flow and re-subscribes from it, so what comes back
 * after a drop is exactly what was missed — the same replay a tab opened the
 * next morning gets, and the same one the daemon answers a `lagged` client
 * with. Nothing is refetched to "make sure", because the cursor is what makes
 * sure.
 *
 * Three ways a connection can end, and they are not the same state. **Refused**
 * (close 4401) is a token this workspace does not accept: retrying is pointless
 * and the surface must say so. **Closed** is this client letting go. Anything
 * else is a **drop**, which reconnects on a backoff — and a drop is also not
 * the daemon being down, a question only an RPC round-trip can answer.
 */

import { LogRing } from './logs'
import type { LogFrame, StreamFrame } from './types'

export const STREAM_PATH = '/api/flow/stream'

/** The close code the daemon refuses a connection with, as distinct from 1006. */
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
  /** Origin of the daemon's web endpoint. Same origin by default. */
  baseUrl?: string
  /** Injected in tests; `WebSocket` against the daemon otherwise. */
  open?: (url: string) => SocketLike
  /** Injected in tests so a backoff never costs a suite its wall clock. */
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

  /**
   * Watch the frames. More than one reader is the normal case — the session
   * reads the journal while a card's console reads that run's chunks — so
   * these are a set and not a slot: a console that unmounted must not be able
   * to take the session's handler down with it.
   */
  onFrame(handler: (frame: StreamFrame) => void): () => void {
    this.frameListeners.add(handler)
    return () => this.frameListeners.delete(handler)
  }

  onStatus(handler: (status: StreamStatus) => void): () => void {
    this.statusListeners.add(handler)
    return () => this.statusListeners.delete(handler)
  }

  /** Where this client has got to on a flow — the cursor a replay starts from. */
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

  /** Stop watching a run whose console is gone. The ring keeps its tail. */
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
    // From the held cursors, not from zero: this is the replay, and it is the
    // same message a first subscription sends.
    for (const flow of this.journals) {
      this.send({ subscribe: 'journal', flow, cursor: this.cursor(flow) })
    }
    for (const key of this.runs) {
      const [flow, runId] = splitRunKey(key)
      this.send({ subscribe: 'logs', flow, run_id: runId })
    }
  }

  private send(message: Record<string, unknown>): void {
    // Dropped rather than queued while the socket is not open — a `send` on a
    // connecting one throws. Nothing is lost by it: every subscription is
    // re-sent on the next open, and a queue would only deliver it twice.
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
        // The daemon dropped what it had queued for this client and said so.
        // The remedy it names is the replay, so ask for it.
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
      // A re-delivered tail is dropped here rather than at the console, so
      // every reader of the ring sees one run, not one run twice.
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
