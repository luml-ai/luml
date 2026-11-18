// Fails every stack test that leaves an error in the browser it did not declare: an error toast,
// a console error or Vue warning, an uncaught error, a failed request or an error response of
// the app's own servers. Both specs import `test` from here, so a new test is guarded at once.
import { test as base, expect, type BrowserContext, type ConsoleMessage } from '@playwright/test'

export { expect }

/** PrimeVue's error toast, in the toast host of the platform and of Flow. */
export const ERROR_TOAST = 'p-toast-message-error'

export type ErrorKind =
  | 'toast'
  | 'console error'
  | 'vue warning'
  | 'page error'
  | 'request failed'
  | 'response'

export interface RecordedError {
  kind: ErrorKind
  /** The message; for a request, its method and the browser's error (or nothing). */
  text: string
  /** Without its query string and fragment. */
  url?: string
  status?: number
}

/** A pattern that names one error a test causes; it must match at least one recorded error. */
export type ExpectedError =
  | { kind: 'toast' | 'console error' | 'vue warning' | 'page error'; text: RegExp }
  | { kind: 'response'; status: number; url: RegExp }
  | { kind: 'request failed'; url: RegExp; text?: RegExp }

type BaselineEntry = ExpectedError & { reason: string }

// Noise that is neither this feature nor ours to fix here, allowed in every test. Each entry was
// looked at and judged; keep the list short.
const BASELINE: BaselineEntry[] = [
  {
    // The platform's sidebar asks api.github.com for the repository's star count and logs the
    // failure; unauthenticated calls are rate-limited (403) on shared runners and dev machines.
    kind: 'console error',
    text: /^AxiosError: [\s\S]*\bgetStarsCount\b/,
    reason: 'GitHub API rate limit, a third party outside this feature',
  },
]

// The app's own servers: platform frontend and backend, MinIO, Azurite, Flow and the proxies in
// front of them all listen on the loopback interface. Anything else is a third party's.
const OWN_HOSTS = new Set(['127.0.0.1', 'localhost'])

// The browser cancels a request (net::ERR_ABORTED) when the page that sent it navigates away or
// closes, when the app aborts it (AbortController, xhr.abort(), a stream reader's cancel, as the
// viewer does once it has the bytes it needs or a view closes) and when a navigation turns into
// a download. Those are the normal end of a request nobody waits for any more, so they are kept
// and not failed on. Every other network error (refused, reset, timed out, empty or invalid
// response, CORS) means a request the app needed did not get an answer, and fails the test.
const CANCELLED = new Set(['net::ERR_ABORTED'])

// Chromium echoes each error response and failed request of a page as a console error ("Failed
// to load resource: ..."); the request itself is recorded, so the echo is not counted twice.
const RESOURCE_ECHO = /^Failed to load resource: /

const BINDING = '__e2eErrorGuard'
const MAX_LINE = 300

/** Drops query strings, fragments and bearer tokens: signed URLs must never reach a log. */
export function redact(text: string): string {
  return text
    .replace(/\b([a-z][a-z0-9+.-]*:\/\/[^\s?#'"<>]*)[?#][^\s'"<>]*/gi, '$1')
    .replace(/\?[^\s'"<>?]*=[^\s'"<>]*/g, '')
    .replace(/#[^\s'"<>#]*token[^\s'"<>]*/gi, '')
    .replace(/\bBearer\s+\S+/gi, 'Bearer <redacted>')
}

function isOwn(url: string): boolean {
  try {
    return OWN_HOSTS.has(new URL(url).hostname)
  } catch {
    return false
  }
}

function matches(expected: ExpectedError, error: RecordedError): boolean {
  if (expected.kind !== error.kind) return false
  if ('status' in expected && expected.status !== error.status) return false
  if ('url' in expected && !expected.url.test(error.url ?? '')) return false
  return !('text' in expected && expected.text && !expected.text.test(error.text))
}

function line(error: RecordedError): string {
  const parts = [`${error.kind}:`, error.text, error.status, error.url].filter(
    (part) => part !== undefined && part !== '',
  )
  const text = redact(parts.join(' ').replace(/\s+/g, ' '))
  return text.length > MAX_LINE ? `${text.slice(0, MAX_LINE)}...` : text
}

function describe(expected: ExpectedError): string {
  const parts: string[] = [expected.kind]
  if ('status' in expected) parts.push(`status ${expected.status}`)
  if ('url' in expected) parts.push(`url ${expected.url}`)
  if ('text' in expected && expected.text) parts.push(`text ${expected.text}`)
  return parts.join(', ')
}

/** Watches every page of a browser context from its first script on. */
export class ErrorGuard {
  readonly recorded: RecordedError[] = []
  readonly cancelled: RecordedError[] = []
  private readonly expected: ExpectedError[] = []
  private readonly toasts = new Map<string, RecordedError>()
  private readonly contexts: BrowserContext[] = []

  /** Declares an error the test causes on purpose; a declaration that never matches fails. */
  expect(expected: ExpectedError): void {
    this.expected.push(expected)
  }

  /** Watches another context of the test too (the test's own context is watched already). */
  async watch(context: BrowserContext): Promise<void> {
    this.contexts.push(context)
    await context.exposeBinding(
      BINDING,
      ({ page }, document: string, index: number, text: string) => {
        const key = `${document}/${index}`
        const known = this.toasts.get(key)
        if (known) known.text = text || known.text
        else {
          const toast: RecordedError = { kind: 'toast', text, url: page?.url().split(/[?#]/)[0] }
          this.toasts.set(key, toast)
          this.recorded.push(toast)
        }
      },
    )
    await context.addInitScript(
      ({ binding, toastClass }) => {
        const report = (window as unknown as Record<string, unknown>)[binding] as (
          document: string,
          index: number,
          text: string,
        ) => Promise<void>
        const documentId = Math.random().toString(36).slice(2)
        const seen: Element[] = []
        const texts: string[] = []
        // Live, so a scan costs nothing while no error toast is shown.
        const live = document.getElementsByClassName(toastClass)
        const read = (toast: Element, index: number) => {
          const text = toast.textContent?.trim() ?? ''
          if (texts[index] === text) return
          texts[index] = text
          void report(documentId, index, text)
        }
        const scan = () => {
          for (const toast of live) {
            // Vue's TransitionGroup adds and removes an empty, hidden clone of each toast that
            // moves when another one comes or goes.
            if (toast.classList.contains('p-toast-message-move')) continue
            const index = seen.includes(toast) ? seen.indexOf(toast) : seen.push(toast) - 1
            read(toast, index)
          }
        }
        // Read again at the end of the test: a toast's text may come after the toast itself.
        Object.assign(window, {
          [`${binding}Rescan`]: () => seen.forEach(read),
        })
        new MutationObserver(scan).observe(document, {
          childList: true,
          subtree: true,
          characterData: true,
        })
      },
      { binding: BINDING, toastClass: ERROR_TOAST },
    )
    context.on('console', (message) => this.onConsole(message))
    context.on('weberror', (error) =>
      this.recorded.push({ kind: 'page error', text: error.error().message }),
    )
    context.on('requestfailed', (request) => {
      if (!isOwn(request.url())) return
      const error: RecordedError = {
        kind: 'request failed',
        text: `${request.method()} ${request.failure()?.errorText ?? ''}`.trim(),
        url: request.url().split(/[?#]/)[0],
      }
      if (CANCELLED.has(request.failure()?.errorText ?? '')) this.cancelled.push(error)
      else this.recorded.push(error)
    })
    context.on('response', (response) => {
      if (response.status() < 400 || !isOwn(response.url())) return
      this.recorded.push({
        kind: 'response',
        text: response.request().method(),
        status: response.status(),
        url: response.url().split(/[?#]/)[0],
      })
    })
  }

  private onConsole(message: ConsoleMessage): void {
    const text = message.text()
    const kind =
      message.type() === 'error'
        ? 'console error'
        : message.type() === 'warning' && text.startsWith('[Vue warn]')
          ? 'vue warning'
          : null
    if (!kind || (kind === 'console error' && RESOURCE_ECHO.test(text))) return
    const source = message.location().url
    this.recorded.push({ kind, text, url: source ? source.split(/[?#]/)[0] : undefined })
  }

  /** Refreshes the text of the toasts still in their page. */
  private async rescanToasts(): Promise<void> {
    for (const context of this.contexts) {
      for (const page of context.pages()) {
        await page
          .evaluate(
            (name) => (window as unknown as Record<string, () => void>)[name]?.(),
            `${BINDING}Rescan`,
          )
          .catch(() => undefined)
      }
    }
  }

  /**
   * The errors nobody declared and the declarations nothing matched, as a message for the test
   * failure; null when there are none. Declarations are not checked when the test failed already
   * (it may have stopped before their cause).
   */
  async problems(testFailed = false): Promise<string | null> {
    await this.rescanToasts()
    const allowed = [...this.expected, ...BASELINE]
    const unexpected = this.recorded.filter(
      (error) => !allowed.some((expected) => matches(expected, error)),
    )
    const unused = testFailed
      ? []
      : this.expected.filter((expected) => !this.recorded.some((error) => matches(expected, error)))
    if (!unexpected.length && !unused.length) return null
    const lines: string[] = []
    if (unexpected.length) {
      lines.push(`${unexpected.length} unexpected error(s) in the browser:`)
      lines.push(...unexpected.map((error) => `  ${line(error)}`))
    }
    if (unused.length) {
      lines.push(`${unused.length} declared error(s) never seen:`)
      lines.push(...unused.map((expected) => `  ${redact(describe(expected))}`))
    }
    if (this.cancelled.length)
      lines.push(`(${this.cancelled.length} cancelled request(s) not counted)`)
    return lines.join('\n')
  }
}

export const test = base.extend<{ errors: ErrorGuard }>({
  errors: [
    async ({ context }, use, testInfo) => {
      const guard = new ErrorGuard()
      await guard.watch(context)
      await use(guard)
      const problems = await guard.problems(testInfo.status !== 'passed')
      if (problems) throw new Error(problems)
    },
    { auto: true },
  ],
})
