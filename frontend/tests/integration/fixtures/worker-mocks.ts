import type { Page } from '@playwright/test'
import {
  WebworkerMessage,
  WEBWORKER_ROUTES_ENUM,
} from '../../../src/lib/data-processing/interfaces'


export type WorkerResponse =
  | unknown
  | { __fn: string } 

type RouteResponses = Partial<Record<WEBWORKER_ROUTES_ENUM, WorkerResponse>>
type MessageResponses = Partial<Record<WebworkerMessage, WorkerResponse>>


export function fn<T = unknown, R = unknown>(handler: (data: T) => R): WorkerResponse {
  return { __fn: handler.toString() }
}

export function createWorkerMocks(page: Page) {
  const routes: RouteResponses = {
    [WEBWORKER_ROUTES_ENUM.TABULAR_DEALLOCATE]: { status: 'success' },
    [WEBWORKER_ROUTES_ENUM.STORE_DEALLOCATE]: { status: 'success' },
    [WEBWORKER_ROUTES_ENUM.PYFUNC_DEINIT]: { status: 'success' },
  }
  const messages: MessageResponses = {
    [WebworkerMessage.LOAD_PYODIDE]: true,
    [WebworkerMessage.INTERRUPT]: undefined,
  }

  const sync = () =>
    page.addInitScript(
      ({ routes, messages }) => {
        const w = window as unknown as {
          __workerRoutes: Record<string, unknown>
          __workerMessages: Record<string, unknown>
          __workerCalls: unknown[]
          __workerPatched?: boolean
          Worker: typeof Worker
        }

        w.__workerRoutes = routes
        w.__workerMessages = messages
        w.__workerCalls = []

        if (w.__workerPatched) return
        w.__workerPatched = true

        const RealWorker = window.Worker

        const resolve = (entry: unknown, data: unknown): unknown => {
          if (
            entry &&
            typeof entry === 'object' &&
            '__fn' in (entry as Record<string, unknown>)
          ) {
            const src = (entry as { __fn: string }).__fn
            
            const fn = new Function(`return (${src})`)()
            return fn(data)
          }
          return entry
        }

        class FakeWorker {
          onmessage: ((e: MessageEvent) => void) | null = null
          onerror: ((e: ErrorEvent) => void) | null = null
          onmessageerror: ((e: MessageEvent) => void) | null = null

          constructor(scriptURL: string | URL) {
            const url = String(scriptURL)
            if (!url.includes('webworker')) {
              return new RealWorker(scriptURL) as unknown as FakeWorker
            }
          }

          postMessage(msg: {
            id: number
            message: string
            payload?: { route?: string; data?: unknown }
          }) {
            const { id, message, payload } = msg
            const route = payload?.route
            const data = payload?.data

            w.__workerCalls.push({ id, message, route, data })

            const respond = async () => {
              try {
                let result: unknown
                if (message === 'invokeRoute' && route) {
                  const entry = w.__workerRoutes[route]
                  result =
                    entry !== undefined
                      ? await resolve(entry, data)
                      : { status: 'error', error_message: `No mock for route ${route}` }
                } else {
                  const entry = w.__workerMessages[message]
                  result = await resolve(entry, data)
                }
                this.onmessage?.({ data: { id, payload: result } } as MessageEvent)
              } catch (err) {
                this.onmessage?.({
                  data: { id, payload: { status: 'error', error_message: String(err) } },
                } as MessageEvent)
              }
            }
            queueMicrotask(respond)
          }

          terminate() {}
          addEventListener() {}
          removeEventListener() {}
          dispatchEvent() {
            return true
          }
        }

        w.Worker = FakeWorker as unknown as typeof Worker
      },
      { routes, messages },
    )

  void sync()

  return {
    onRoute: async (route: WEBWORKER_ROUTES_ENUM, response: WorkerResponse) => {
      routes[route] = response
      await sync()
    },
    onMessage: async (message: WebworkerMessage, response: WorkerResponse) => {
      messages[message] = response
      await sync()
    },
    setRoute: async (route: WEBWORKER_ROUTES_ENUM, response: WorkerResponse) => {
      routes[route] = response
      await page.evaluate(
        ({ route, response }) => {
          ;(window as unknown as { __workerRoutes: Record<string, unknown> }).__workerRoutes[
            route
          ] = response
        },
        { route, response },
      )
    },
    getCalls: () =>
      page.evaluate(
        () => (window as unknown as { __workerCalls: unknown[] }).__workerCalls ?? [],
      ),
  }
}

export type WorkerMocks = ReturnType<typeof createWorkerMocks>
export { fn as workerFn }