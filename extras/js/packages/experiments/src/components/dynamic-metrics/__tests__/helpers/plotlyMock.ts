import { vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'

export type PlotEventHandler = (event: Record<string, unknown>) => void

export interface ReactCall {
  element: HTMLElement
  traces: Array<Record<string, unknown>>
  layout: Record<string, unknown>
  config: Record<string, unknown>
}

interface PendingDraw {
  resolve: () => void
  reject: (error: Error) => void
}

/**
 * A Plotly stand-in that records `react` calls and the handlers charts register. After
 * `holdDraws()` each `react` stays pending until `settleDraw` resolves or rejects it.
 */
export function createPlotlyMock() {
  const calls: ReactCall[] = []
  const handlers = new Map<HTMLElement, Map<string, PlotEventHandler>>()
  const pendingDraws: PendingDraw[] = []
  let drawsHeld = false
  const react = vi.fn(
    async (
      element: HTMLElement & { on?: unknown },
      traces: Array<Record<string, unknown>>,
      layout: Record<string, unknown>,
      config: Record<string, unknown>,
    ) => {
      calls.push({ element, traces, layout, config })
      if (!handlers.has(element)) {
        const own = new Map<string, PlotEventHandler>()
        handlers.set(element, own)
        element.on = (name: string, handler: PlotEventHandler) => own.set(name, handler)
      }
      if (drawsHeld) {
        await new Promise<void>((resolve, reject) => pendingDraws.push({ resolve, reject }))
      }
    },
  )
  const plotly = {
    react,
    newPlot: vi.fn(),
    purge: vi.fn(),
    Plots: { resize: vi.fn() },
  }

  function lastCall(element?: HTMLElement): ReactCall {
    const matching = element ? calls.filter((call) => call.element === element) : calls
    const call = matching[matching.length - 1]
    if (!call) throw new Error('Plotly.react was not called')
    return call
  }

  function fire(element: HTMLElement, name: string, event: Record<string, unknown> = {}): void {
    const handler = handlers.get(element)?.get(name)
    if (!handler) throw new Error(`No '${name}' handler`)
    handler(event)
  }

  function reset(): void {
    calls.length = 0
    handlers.clear()
  }

  function holdDraws(): void {
    drawsHeld = true
  }

  /** Settles the oldest pending draw. */
  function settleDraw(error?: Error): void {
    const draw = pendingDraws.shift()
    if (!draw) throw new Error('No pending draw')
    if (error) draw.reject(error)
    else draw.resolve()
  }

  function releaseDraws(): void {
    drawsHeld = false
    while (pendingDraws.length) settleDraw()
  }

  return {
    plotly,
    calls,
    pendingDraws,
    lastCall,
    fire,
    reset,
    holdDraws,
    settleDraw,
    releaseDraws,
  }
}

/** Lets the store's debounce (0 ms in tests), the fake reads and Plotly renders run. */
export async function settle(rounds = 6): Promise<void> {
  for (let round = 0; round < rounds; round++) {
    await new Promise((resolve) => setTimeout(resolve, 0))
    await flushPromises()
  }
}

/** A controllable IntersectionObserver: `show(element)` reports it as visible. */
export function installIntersectionObserver() {
  const observers = new Set<FakeObserver>()

  class FakeObserver {
    readonly elements = new Set<Element>()
    constructor(private readonly callback: IntersectionObserverCallback) {
      observers.add(this)
    }
    observe(element: Element) {
      this.elements.add(element)
    }
    unobserve(element: Element) {
      this.elements.delete(element)
    }
    disconnect() {
      this.elements.clear()
      observers.delete(this)
    }
    takeRecords() {
      return []
    }
    report(element: Element, isIntersecting: boolean) {
      const entry = { target: element, isIntersecting } as IntersectionObserverEntry
      this.callback([entry], this as unknown as IntersectionObserver)
    }
  }

  vi.stubGlobal('IntersectionObserver', FakeObserver)

  function observed(): Element[] {
    return [...observers].flatMap((observer) => [...observer.elements])
  }

  function setVisible(element: Element, visible: boolean): void {
    for (const observer of observers) {
      if (observer.elements.has(element)) observer.report(element, visible)
    }
  }

  return { observed, setVisible }
}
