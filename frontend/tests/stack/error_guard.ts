// Fails every stack test that leaves an error in the browser it did not declare: an error toast
// or error shown in the page, a console error or Vue warning, an uncaught error, a failed request
// or an error response of the app's own servers, and any request to the internet. Both specs
// import `test` from here, so a new test is guarded at once.
import {
  test as base,
  expect,
  type Browser,
  type BrowserContext,
  type ConsoleMessage,
  type Request,
} from '@playwright/test'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { createServer } from 'node:https'
import type { AddressInfo } from 'node:net'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

export { expect }

/** PrimeVue's error toast, in the toast host of the platform and of Flow. */
export const ERROR_TOAST = 'p-toast-message-error'

/**
 * Errors the views show in the page: a chart's read error icon, an error notice of an experiment
 * (warning and info notices are not errors) and an attachment preview that failed.
 */
export const ERROR_STATES = [
  '[data-testid="chart-error"]',
  '[data-testid="experiment-status-notice"].p-message-error',
  '.state-content.error',
  '.table-preview > .error',
].join(', ')

export type ErrorKind =
  | 'toast'
  | 'error state'
  | 'console error'
  | 'vue warning'
  | 'page error'
  | 'request failed'
  | 'response'
  | 'external request'

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
  | { kind: 'toast' | 'error state' | 'console error' | 'vue warning' | 'page error'; text: RegExp }
  | { kind: 'response'; status: number; url: RegExp }
  | { kind: 'request failed'; url: RegExp; text?: RegExp }

interface ThirdPartyAnswer {
  host: string
  path: RegExp
  contentType: string
  body: string
  reason: string
}

// The only third-party calls the apps make in these tests, answered by a local server (see
// `thirdPartyPort`) with what a normal user would get; the browser resolves every other host
// on the internet to nothing, and the guard fails a test that asks for one.
export const THIRD_PARTY: ThirdPartyAnswer[] = [
  {
    host: 'api.github.com',
    path: /^\/repos\/luml-ai\/luml$/,
    contentType: 'application/json',
    body: JSON.stringify({ stargazers_count: 0 }),
    reason: "the platform's sidebar shows the repository's star count",
  },
  {
    host: 'fonts.googleapis.com',
    path: /^\/css$/,
    contentType: 'text/css',
    body: '',
    reason: 'both apps import the Inter font; with no font the text falls back to a system font',
  },
  {
    host: 'cdn.jsdelivr.net',
    path: /^\/npm\/@vue-flow\/core@[\d.]+\/dist\/(style|theme-default)\.css$/,
    contentType: 'text/css',
    body: '',
    reason: "the platform imports Vue Flow's styles; no view under test draws a flow graph",
  },
]

// The app's own servers: platform frontend and backend, MinIO, Azurite, Flow and the proxies in
// front of them all listen on the loopback interface. Anything else is a third party's.
const OWN_HOSTS = new Set(['127.0.0.1', 'localhost'])
const ANSWERED_HOSTS = new Set(THIRD_PARTY.map((answer) => answer.host))

// The longest the end of a test waits for responses still on the way, which may be errors.
const SETTLE_MS = 5_000

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

/**
 * Drops query strings, fragments, signatures, keys and tokens: signed URLs and credentials must
 * never reach a log.
 */
export function redact(text: string): string {
  return text
    .replace(/\b([a-z][a-z0-9+.-]*:\/\/[^\s?#'"<>]*)[?#][^\s'"<>]*/gi, '$1')
    .replace(/\?[^\s'"<>?]*=[^\s'"<>]*/g, '')
    .replace(/#[^\s'"<>#]*token[^\s'"<>]*/gi, '')
    .replace(
      /\b(sig|signature|X-Amz-[\w-]+|AccountKey|SharedAccessSignature|token|Credential)=[^\s&;'"]+/gi,
      '$1=<redacted>',
    )
    .replace(/\bAuthorization:\s*\S+\s+\S+/gi, 'Authorization: <redacted>')
    .replace(/\bBearer\s+\S+/gi, 'Bearer <redacted>')
}

function hostOf(url: string): string | null {
  try {
    return new URL(url).hostname
  } catch {
    return null
  }
}

/** A request the guard checks the answer of: to the app's servers or an answered third party. */
function isServed(url: string): boolean {
  const host = hostOf(url)
  return host !== null && (OWN_HOSTS.has(host) || ANSWERED_HOSTS.has(host))
}

/** A request to the internet: anything over HTTP that is neither the app's nor answered here. */
function isExternal(url: string): boolean {
  return /^(https?|wss?):/.test(url) && !isServed(url)
}

/**
 * Starts the local server of `THIRD_PARTY`. HTTPS, as the apps call those hosts; its certificate
 * is made here (openssl) and the browser accepts it (see `thirdPartyLaunchArgs`).
 */
async function serveThirdParty(): Promise<{ port: number; close: () => Promise<void> }> {
  const dir = mkdtempSync(join(tmpdir(), 'luml-e2e-third-party-'))
  try {
    const certificate = ['-days', '1', '-subj', '/CN=e2e-third-party', '-nodes']
    const files = ['-keyout', join(dir, 'key.pem'), '-out', join(dir, 'cert.pem')]
    execFileSync('openssl', ['req', '-x509', '-newkey', 'rsa:2048', ...certificate, ...files], {
      stdio: 'pipe',
    })
    const key = readFileSync(join(dir, 'key.pem'))
    const cert = readFileSync(join(dir, 'cert.pem'))
    const server = createServer({ key, cert }, (request, response) => {
      const host = (request.headers.host ?? '').split(':')[0]
      const path = (request.url ?? '/').split('?')[0]!
      const answer = THIRD_PARTY.find((item) => item.host === host && item.path.test(path))
      response.writeHead(answer ? 200 : 404, {
        'content-type': answer?.contentType ?? 'text/plain',
        // As the real services answer: the platform's pages are cross-origin isolated (COEP).
        'access-control-allow-origin': '*',
        'cross-origin-resource-policy': 'cross-origin',
      })
      response.end(answer?.body ?? 'not a known third-party call')
    })
    await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve))
    const { port } = server.address() as AddressInfo
    return {
      port,
      close: () => new Promise<void>((resolve) => server.close(() => resolve())),
    }
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
}

/**
 * Chromium resolves the answered hosts to the local server and every other host to nothing
 * (loopback names excepted). A route would do too, but any route turns the browser's HTTP cache
 * off and sends every request of the context through the test process, storage reads included.
 */
function thirdPartyLaunchArgs(port: number): string[] {
  const rules = [
    ...THIRD_PARTY.map((answer) => `MAP ${answer.host} 127.0.0.1:${port}`),
    'MAP * ~NOTFOUND',
    ...[...OWN_HOSTS].map((host) => `EXCLUDE ${host}`),
  ]
  return [`--host-resolver-rules=${rules.join(', ')}`, '--ignore-certificate-errors']
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
  private readonly shown = new Map<string, RecordedError>()
  private readonly contexts: BrowserContext[] = []
  /** Requests whose answer has not come yet; it may be an error response. */
  private readonly unanswered = new Set<Request>()
  private answered: () => void = () => undefined

  /** Declares an error the test causes on purpose; a declaration that never matches fails. */
  expect(expected: ExpectedError): void {
    this.expected.push(expected)
  }

  /** Watches another context of the test too (the fixture watches every context it can see). */
  async watch(context: BrowserContext): Promise<void> {
    if (this.contexts.includes(context)) return
    this.contexts.push(context)
    await context.exposeBinding(
      BINDING,
      ({ page }, document: string, index: number, kind: ErrorKind, text: string) => {
        const key = `${document}/${index}`
        const known = this.shown.get(key)
        if (known) known.text = text || known.text
        else {
          const error: RecordedError = { kind, text, url: page?.url().split(/[?#]/)[0] }
          this.shown.set(key, error)
          this.recorded.push(error)
        }
      },
    )
    await context.addInitScript(
      ({ binding, toastClass, errorStates }) => {
        const report = (window as unknown as Record<string, unknown>)[binding] as (
          document: string,
          index: number,
          kind: string,
          text: string,
        ) => Promise<void>
        const documentId = Math.random().toString(36).slice(2)
        const seen: Element[] = []
        const kinds: string[] = []
        const texts: string[] = []
        const reports = new Set<Promise<void>>()
        // Live, so a scan costs nothing while no error toast is shown.
        const toasts = document.getElementsByClassName(toastClass)
        const textOf = (element: Element) => {
          // The chart's error icon has no text (its message is a tooltip): named by its chart.
          if (element.matches('[data-testid="chart-error"]'))
            return `chart ${element.closest('[data-metric-key]')?.getAttribute('data-metric-key')}`
          return element.textContent?.trim() ?? ''
        }
        const read = (element: Element, index: number) => {
          // Gone from the page: its last text stands (a chart's name is no longer found).
          if (!element.isConnected) return
          const text = textOf(element)
          if (texts[index] === text) return
          texts[index] = text
          const sent = report(documentId, index, kinds[index]!, text).catch(() => undefined)
          reports.add(sent)
          void sent.then(() => reports.delete(sent))
        }
        const note = (element: Element, kind: string) => {
          let index = seen.indexOf(element)
          if (index === -1) {
            index = seen.push(element) - 1
            kinds[index] = kind
          }
          read(element, index)
        }
        const scan = () => {
          for (const toast of toasts) {
            // Vue's TransitionGroup adds and removes an empty, hidden clone of each toast that
            // moves when another one comes or goes.
            if (!toast.classList.contains('p-toast-message-move')) note(toast, 'toast')
          }
          for (const element of document.querySelectorAll(errorStates)) note(element, 'error state')
        }
        // At the end of the test: an error's text may come after the error itself, and the
        // reports sent last must have arrived.
        Object.assign(window, {
          [`${binding}Drain`]: async () => {
            scan()
            seen.forEach(read)
            await Promise.all(reports)
          },
        })
        // Classes too: a toast may become an error toast by its class alone.
        new MutationObserver(scan).observe(document, {
          childList: true,
          subtree: true,
          characterData: true,
          attributes: true,
          attributeFilter: ['class'],
        })
      },
      { binding: BINDING, toastClass: ERROR_TOAST, errorStates: ERROR_STATES },
    )
    context.on('console', (message) => this.onConsole(message))
    context.on('weberror', (error) =>
      this.recorded.push({ kind: 'page error', text: error.error().message }),
    )
    context.on('request', (request) => {
      if (isServed(request.url())) this.unanswered.add(request)
      else if (isExternal(request.url()))
        this.recorded.push({
          kind: 'external request',
          text: request.method(),
          url: request.url().split(/[?#]/)[0],
        })
    })
    context.on('requestfailed', (request) => {
      this.answer(request)
      if (!isServed(request.url())) return
      const error: RecordedError = {
        kind: 'request failed',
        text: `${request.method()} ${request.failure()?.errorText ?? ''}`.trim(),
        url: request.url().split(/[?#]/)[0],
      }
      if (CANCELLED.has(request.failure()?.errorText ?? '')) this.cancelled.push(error)
      else this.recorded.push(error)
    })
    context.on('response', (response) => {
      this.answer(response.request())
      if (response.status() < 400 || !isServed(response.url())) return
      this.recorded.push({
        kind: 'response',
        text: response.request().method(),
        status: response.status(),
        url: response.url().split(/[?#]/)[0],
      })
    })
  }

  private answer(request: Request): void {
    if (this.unanswered.delete(request)) this.answered()
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

  /**
   * Gives errors still on the way a bounded chance to arrive: what each open page has shown and
   * reported, answers to requests in flight (up to SETTLE_MS, not longer, since a test may leave
   * a read held), then the pages again for what those answers showed. Events of a page come in
   * order, so what it logged or sent before a drain has arrived once the drain returns.
   */
  private async settle(): Promise<void> {
    await this.drainPages()
    const deadline = Date.now() + SETTLE_MS
    for (const request of this.unanswered) {
      // A closed page's requests get no more events. A worker's request has no frame.
      try {
        if (request.frame().page().isClosed()) this.unanswered.delete(request)
      } catch {
        continue
      }
    }
    if (!this.unanswered.size) return
    while (this.unanswered.size && Date.now() < deadline) {
      await new Promise<void>((resolve) => {
        const timer = setTimeout(resolve, deadline - Date.now())
        this.answered = () => {
          clearTimeout(timer)
          resolve()
        }
      })
    }
    this.answered = () => undefined
    await this.drainPages()
  }

  private async drainPages(): Promise<void> {
    for (const context of this.contexts) {
      for (const page of context.pages()) {
        await page
          .evaluate(
            (name) => (window as unknown as Record<string, () => Promise<void>>)[name]?.(),
            `${BINDING}Drain`,
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
    await this.settle()
    const unexpected = this.recorded.filter(
      (error) => !this.expected.some((expected) => matches(expected, error)),
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

const unwatchedNewContext = new WeakMap<Browser, Browser['newContext']>()

/** A context the fixture's guard does not watch, for a test of the guard itself. */
export async function newUnwatchedContext(browser: Browser): Promise<BrowserContext> {
  const newContext = unwatchedNewContext.get(browser) ?? browser.newContext
  return newContext.call(browser)
}

export const test = base.extend<{ errors: ErrorGuard }, { thirdPartyPort: number }>({
  thirdPartyPort: [
    async ({}, use) => {
      const server = await serveThirdParty()
      await use(server.port)
      await server.close()
    },
    { scope: 'worker' },
  ],
  launchOptions: [
    async ({ launchOptions, thirdPartyPort }, use) => {
      const args = [...(launchOptions.args ?? []), ...thirdPartyLaunchArgs(thirdPartyPort)]
      await use({ ...launchOptions, args })
    },
    { scope: 'worker' },
  ],
  errors: [
    async ({ context, browser }, use, testInfo) => {
      const guard = new ErrorGuard()
      await guard.watch(context)
      // Contexts the test opens itself are watched too (browser.newPage opens one this way).
      const newContext = browser.newContext
      unwatchedNewContext.set(browser, newContext)
      browser.newContext = async (options) => {
        const opened = await newContext.call(browser, options)
        await guard.watch(opened)
        return opened
      }
      try {
        await use(guard)
      } finally {
        browser.newContext = newContext
        unwatchedNewContext.delete(browser)
      }
      const problems = await guard.problems(testInfo.status !== 'passed')
      if (problems) throw new Error(problems)
    },
    { auto: true },
  ],
})
