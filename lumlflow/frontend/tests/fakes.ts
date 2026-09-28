/**
 * A daemon and a socket that answer, so the specs can assert the client's own
 * contract rather than a server's. Shared by every live-surface spec: one
 * definition of what the daemon looks like keeps two suites from disagreeing
 * about the wire the product speaks.
 */

import { nextTick } from 'vue'
import { expect } from 'vitest'
import type { VueWrapper } from '@vue/test-utils'

import { FlowApi, FlowApiError } from '@/flow/api/client'
import { FlowStream } from '@/flow/api/stream'
import type { SocketLike } from '@/flow/api/stream'
import type {
  CellDetail,
  CellSummary,
  FlowStatus,
  StoredPreview,
  StreamFrame,
  Transaction,
} from '@/flow/api/types'
import { SETTLE_MS, useFlowSession } from '@/flow/workbench/live/useFlowSession'
import type { FlowSessionHandle } from '@/flow/workbench/live/useFlowSession'

export const FLOW = 'churn.flow'

export class FakeSocket implements SocketLike {
  sent: string[] = []
  onopen: (() => void) | null = null
  onmessage: ((event: { data: unknown }) => void) | null = null
  onclose: ((event: { code: number }) => void) | null = null
  onerror: ((event: unknown) => void) | null = null

  send(data: string): void {
    this.sent.push(data)
  }

  close(): void {
    this.onclose?.({ code: 1000 })
  }

  open(): void {
    this.onopen?.()
  }

  deliver(frame: StreamFrame): void {
    this.onmessage?.({ data: JSON.stringify(frame) })
  }

  drop(code = 1006): void {
    this.onclose?.({ code })
  }

  get messages(): Record<string, unknown>[] {
    return this.sent.map((line) => JSON.parse(line) as Record<string, unknown>)
  }
}

export interface Daemon {
  api: FlowApi
  /** For surfaces that build their own client: stub `fetch` with this. */
  transport: typeof globalThis.fetch
  calls: { method: string; params: Record<string, unknown> }[]
  down: { value: boolean }
}

export type Handlers = Record<string, (params: Record<string, unknown>) => unknown>

/**
 * `down` is nobody answering. A handler that throws a `FlowApiError` is the
 * other failure entirely — the daemon naming something about the request — and
 * it crosses the wire as an error body, the way the real one does. A fake that
 * collapsed the two would let a surface pass while reporting the wrong failure.
 */
export function fakeDaemon(handlers: Handlers = {}): Daemon {
  const calls: { method: string; params: Record<string, unknown> }[] = []
  const down = { value: false }
  const transport: typeof globalThis.fetch = async (_url, init) => {
    const body = JSON.parse(String(init?.body)) as {
      method: string
      params: Record<string, unknown>
    }
    calls.push(body)
    if (down.value) throw new TypeError('failed to fetch')
    let result: unknown
    try {
      result = (await handlers[body.method]?.(body.params)) ?? {}
    } catch (refused) {
      if (!(refused instanceof FlowApiError)) throw refused
      return {
        ok: false,
        status: refused.status,
        json: async () => ({ error: { message: refused.message, kind: refused.kind } }),
      } as unknown as Response
    }
    return {
      ok: true,
      status: 200,
      json: async () => ({ result }),
    } as unknown as Response
  }
  return { api: new FlowApi({ token: 'the-token', fetch: transport }), transport, calls, down }
}

export function flowStatus(overrides: Partial<FlowStatus> = {}): FlowStatus {
  return {
    flow: 'churn',
    flow_id: 'flow-1',
    path: FLOW,
    branch: 'main',
    checked_out: true,
    agent: null,
    kernel: { state: 'running', restart_required: false, behind: [] },
    settings: { reactivity: 'auto', eager_cost_threshold_s: 5 },
    cells: [],
    disk_bytes: 4096,
    hygiene: [],
    ...overrides,
  }
}

export function cellSummary(slug: string, overrides: Partial<CellSummary> = {}): CellSummary {
  return {
    uid: slug,
    slug,
    state: 'synced',
    causes: [],
    upstream: [],
    transitive: false,
    outputs: ['result'],
    kinds: { result: 'metric' },
    primary: 'result',
    consumes: {},
    note: false,
    external: false,
    flags: [],
    cost_seconds: 1,
    older_env: false,
    reused: false,
    created_step: 1,
    order: String(overrides.created_step ?? 1),
    changed_step: 1,
    eager: false,
    auto_declined: null,
    tracker: null,
    ...overrides,
  }
}

export function cellDetail(slug: string, overrides: Partial<CellDetail> = {}): CellDetail {
  return {
    ...cellSummary(slug),
    branch: 'main',
    definition_hash: 'def-hash',
    source: `class ${slug}:\n    """A cell."""\n`,
    doc: 'A cell.',
    params: {},
    author: 'user',
    produces: { result: { type: 'asset', kind: null, persist: true } },
    materialized: [
      {
        name: 'result',
        kind: 'metric',
        kind_source: 'matcher',
        declared: 'asset',
        size: 32,
        persisted: true,
      },
    ],
    sdk_version_warning: null,
    error: null,
    failed_by: null,
    provenance: {
      created_by: 'user',
      created_step: 1,
      last_edited_by: 'user',
      step: 2,
      intent: 'edited a cell',
      attribution_uncertain: false,
    },
    ...overrides,
  }
}

/** A preview as the kernel stores one: a versioned envelope over blocks. */
export function storedPreview(kind: string, blocks: unknown[], schema = 1): StoredPreview {
  return { schema, kind, blocks, truncated: false }
}

export function transaction(step: number, overrides: Partial<Transaction> = {}): Transaction {
  return {
    step,
    ts: `2026-08-13T09:0${step}:00Z`,
    actor: 'claude-1',
    intent: `edited features (${step})`,
    offline: false,
    settled: false,
    branch: 'branch-id',
    ops: [],
    ...overrides,
  }
}

export interface Attached {
  session: FlowSessionHandle
  socket: FakeSocket
  stream: FlowStream
  daemon: Daemon
  sockets: FakeSocket[]
  reconnects: (() => void)[]
}

export async function attach(
  options: { status?: FlowStatus; handlers?: Handlers; seenStep?: number } = {},
): Promise<Attached> {
  const daemon = fakeDaemon({
    'flow.open': () => options.status ?? flowStatus(),
    ping: () => ({ workspace: '/tmp/project', pid: 1, web: null }),
    ...options.handlers,
  })
  const sockets: FakeSocket[] = []
  const reconnects: (() => void)[] = []
  const stream = new FlowStream({
    token: 'the-token',
    open: () => {
      const socket = new FakeSocket()
      sockets.push(socket)
      return socket
    },
    schedule: (run) => reconnects.push(run),
  })
  const session = useFlowSession({
    api: daemon.api,
    stream,
    flow: 'churn',
    seenStep: options.seenStep,
  })
  await session.attach()
  sockets[0].open()
  return { session, socket: sockets[0], stream, daemon, sockets, reconnects }
}

/**
 * Let the fake transport's promise chain and the watchers it wakes finish.
 *
 * Deep enough for a surface that reads several things in sequence — a card
 * pulls its source, then a preview, then a log artifact, each a round trip —
 * because a half-settled turn asserts against a screen still filling in.
 */
export async function settle(): Promise<void> {
  for (let round = 0; round < 4; round += 1) {
    for (let turn = 0; turn < 16; turn += 1) await Promise.resolve()
    await nextTick()
  }
}

/**
 * The same, plus the session's quiet point.
 *
 * A run of transactions is one movement of the store, so the reads that depend
 * on the journal wait for the frames to stop before going out again. A test
 * that delivers transactions without the catch-up frame that ends a real
 * subscription cycle has no other end-of-burst to wait for.
 */
export async function settleJournal(): Promise<void> {
  await settle()
  await new Promise((resume) => setTimeout(resume, SETTLE_MS + 20))
  await settle()
}

/**
 * The cell card's overflow menu. Two controls ride the op row — the run and
 * this — and every other verb is one deliberate click behind it.
 */
export async function openCardMenu(wrapper: VueWrapper): Promise<void> {
  const more = wrapper
    .findAll('button')
    .find((button) => button.attributes('aria-label') === 'more')
  expect(more, 'no overflow control on the card').toBeTruthy()
  await more?.trigger('click')
  await settle()
}

/** Clicks a menu item by its label, wherever the overlay was teleported to. */
export async function clickMenuItem(label: string): Promise<void> {
  const item = [...document.body.querySelectorAll('[role="menuitem"] > div')].find((node) =>
    node.textContent?.trim().startsWith(label),
  )
  expect(item, `no menu item reading "${label}"`).toBeTruthy()
  ;(item as HTMLElement | null)?.click()
  await settle()
}

/**
 * Opens a disclosure by its header label. Secondary sections start collapsed
 * and render nothing until asked for, so a spec that reads one opens it the
 * way a reader would — including from the keyboard, which the header is.
 */
export async function openPanel(wrapper: VueWrapper, label: string): Promise<void> {
  const header = wrapper
    .findAll('[data-pc-name="accordionheader"]')
    .find((node) => node.text().startsWith(label))
  expect(header, `no "${label}" section to open`).toBeTruthy()
  if (header?.attributes('aria-expanded') !== 'true') {
    await header?.trigger('click')
    await settle()
  }
}
