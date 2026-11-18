// Controls a throttle_proxy.mjs instance that run.sh started in front of storage or Flow.

export interface ProxyConfig {
  latencyMs?: number
  bytesPerSecond?: number
  throttleMatching?: string | null
  stallMatching?: string | null
  stripRange?: boolean
  refuseSeen?: boolean
  refuseMatching?: string | null
  refuseOverlapping?: [number, number] | null
}

export interface ProxiedRequest {
  method: string
  path: string
  range: string | null
  status: number
  bytes: number
  stalled: boolean
  startedAt: number
  firstByteAt: number
  endedAt: number
}

/** About 1.5 Mbit/s with 150 ms per request: a weak mobile link. */
export const SLOW_LINK: ProxyConfig = { latencyMs: 150, bytesPerSecond: 190_000 }
/** About 0.5 Mbit/s with 300 ms per request. */
export const VERY_SLOW_LINK: ProxyConfig = { latencyMs: 300, bytesPerSecond: 62_500 }

export class ThrottleProxy {
  constructor(readonly port: string) {}

  private async call(method: string, path: string, body?: unknown): Promise<Response> {
    const response = await fetch(`http://127.0.0.1:${this.port}/__e2e/${path}`, {
      method,
      headers: body === undefined ? {} : { 'content-type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    if (!response.ok) throw new Error(`proxy ${path}: ${response.status}`)
    return response
  }

  async reset(): Promise<void> {
    await this.call('POST', 'reset')
  }

  async configure(config: ProxyConfig): Promise<void> {
    await this.call('POST', 'config', config)
  }

  /** Answers the requests held now; stallMatching still holds the later ones. */
  async release(): Promise<void> {
    await this.call('POST', 'release')
  }

  async requests(): Promise<ProxiedRequest[]> {
    return (await (await this.call('GET', 'log')).json()) as ProxiedRequest[]
  }
}
