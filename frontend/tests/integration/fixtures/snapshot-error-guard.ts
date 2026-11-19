// Fails a snapshot spec's test on a console error or an uncaught error or rejection it did not
// declare, the worker's included, and on a declared one that never happened. The conventions
// follow tests/stack/error_guard.ts, without the app's toasts and requests: these specs drive the
// worker through a harness page and make storage fail on purpose.
import { test as base, expect, type BrowserContext, type ConsoleMessage } from '@playwright/test'

export { expect }

export interface ExpectedError {
  kind: 'console error' | 'page error'
  text: RegExp
}

interface RecordedError {
  kind: ExpectedError['kind']
  text: string
}

// The browser's own console report of an error response or a refused request (WebKit names
// the URL in it). The specs assert those requests themselves; the report is not the page's.
export const BROWSER_NETWORK_REPORT =
  /^Failed to load resource: |^(Fetch API|XMLHttpRequest) cannot load |^Origin \S+ is not allowed by Access-Control-Allow-Origin\b/

// Firefox and WebKit report an unhandled rejection in a worker only as a console error.
const FIREFOX_UNCAUGHT = /^\[JavaScript Error: "(.*)" \{file: .*\}\]$/s
const WEBKIT_UNCAUGHT = /^Unhandled Promise Rejection: (.*)$/s

const WORKER_ERROR_BINDING = '__snapshotErrorGuardWorkerError'

export class SnapshotErrorGuard {
  readonly recorded: RecordedError[] = []
  private readonly expected: ExpectedError[] = []

  /** Declares an error the test causes on purpose; a declaration that never matches fails. */
  expect(expected: ExpectedError): void {
    this.expected.push(expected)
  }

  onConsole(message: ConsoleMessage): void {
    if (message.type() !== 'error' || BROWSER_NETWORK_REPORT.test(message.text())) return
    const uncaught = FIREFOX_UNCAUGHT.exec(message.text()) ?? WEBKIT_UNCAUGHT.exec(message.text())
    if (uncaught) this.recorded.push({ kind: 'page error', text: uncaught[1]! })
    else this.recorded.push({ kind: 'console error', text: message.text() })
  }

  onPageError(error: Error): void {
    this.recorded.push({ kind: 'page error', text: `${error.name}: ${error.message}` })
  }

  /**
   * Playwright reports an uncaught error of a worker as a page error only when the page leaves
   * the worker's error event unhandled (Chromium and Firefox). The page sees every worker's
   * error event in each engine, so a listener added at the worker's creation reports each one.
   */
  async watchWorkers(context: BrowserContext): Promise<void> {
    await context.exposeBinding(WORKER_ERROR_BINDING, (_source, text: string) => {
      this.recorded.push({ kind: 'page error', text })
    })
    await context.addInitScript((binding) => {
      const report = (window as unknown as Record<string, (text: string) => Promise<void>>)[
        binding
      ]!
      const NativeWorker = window.Worker
      window.Worker = class extends NativeWorker {
        constructor(url: string | URL, options?: WorkerOptions) {
          super(url, options)
          this.addEventListener('error', (event) => {
            void report(event.message || 'worker error without a message').catch(() => undefined)
          })
        }
      }
    }, WORKER_ERROR_BINDING)
  }

  /** Not checked for unused declarations when the test failed: it may have stopped before. */
  problems(testFailed: boolean): string | null {
    const matches = (expected: ExpectedError, error: RecordedError) =>
      expected.kind === error.kind && expected.text.test(error.text)
    const unexpected = this.recorded.filter(
      (error) => !this.expected.some((expected) => matches(expected, error)),
    )
    const unused = testFailed
      ? []
      : this.expected.filter((expected) => !this.recorded.some((error) => matches(expected, error)))
    if (!unexpected.length && !unused.length) return null
    return [
      ...unexpected.map((error) => `unexpected ${error.kind}: ${error.text.slice(0, 300)}`),
      ...unused.map((expected) => `declared ${expected.kind} never seen: ${expected.text}`),
    ].join('\n')
  }
}

export const test = base.extend<{ errors: SnapshotErrorGuard }>({
  errors: [
    async ({ context }, use, testInfo) => {
      const guard = new SnapshotErrorGuard()
      context.on('console', (message) => guard.onConsole(message))
      context.on('weberror', (webError) => guard.onPageError(webError.error()))
      await guard.watchWorkers(context)
      await use(guard)
      // A round trip to each page: the worker errors it reported before have arrived.
      for (const page of context.pages())
        await page.evaluate(() => undefined).catch(() => undefined)
      const problems = guard.problems(testInfo.status !== testInfo.expectedStatus)
      if (problems) throw new Error(problems)
    },
    { auto: true },
  ],
})
