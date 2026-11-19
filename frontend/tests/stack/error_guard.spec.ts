import type { BrowserContext, Page } from '@playwright/test'
import {
  ErrorGuard,
  ERROR_TOAST,
  expect,
  newUnwatchedContext,
  redact,
  test,
  THIRD_PARTY,
} from './error_guard'

// The guard itself, on a page of its own served by the test (no stack needed): it reports each
// kind of error, keeps signed query strings out of its message, allows what a test declares and
// fails a declaration that nothing matched.

const APP = 'http://127.0.0.1:9'

async function serveApp(context: BrowserContext) {
  await context.route(`${APP}/**`, async (route) => {
    const path = new URL(route.request().url()).pathname
    if (path === '/app') return route.fulfill({ contentType: 'text/html', body: '<p>app</p>' })
    if (path === '/refused') return route.abort('connectionrefused')
    if (path === '/slow') return new Promise(() => undefined)
    if (path === '/late') {
      await new Promise((resolve) => setTimeout(resolve, 1_000))
      return route.fulfill({ status: 503, body: 'late' })
    }
    return route.fulfill({ status: 500, body: 'failed' })
  })
}

/** One error of every kind, one cancelled request and one toast's move clone. */
async function causeErrors(page: Page) {
  await page.evaluate(async (toastClass) => {
    const toast = document.createElement('div')
    toast.className = toastClass
    document.body.append(toast)
    await new Promise((resolve) => setTimeout(resolve, 50))
    toast.textContent = 'Toast text'
    const clone = document.createElement('div')
    clone.className = `${toastClass} p-toast-message-move`
    clone.textContent = 'Clone'
    document.body.append(clone)
    await new Promise((resolve) => setTimeout(resolve, 50))
    toast.remove()
    clone.remove()
    console.error('Console text')
    console.warn('[Vue warn]: Warning text')
    console.warn('An ordinary warning')
    setTimeout(() => {
      throw new Error('Thrown text')
    })
    void Promise.reject(new Error('Rejected text'))
    await fetch('/data?X-Amz-Signature=secret-signature&sig=secret-sas')
    await fetch('/refused').catch(() => undefined)
    const controller = new AbortController()
    const cancelled = fetch('/slow', { signal: controller.signal }).catch(() => undefined)
    await new Promise((resolve) => setTimeout(resolve, 100))
    controller.abort()
    await cancelled
    const worker = new Worker(
      URL.createObjectURL(
        new Blob(["console.error('Worker text'); postMessage(0)"], { type: 'text/javascript' }),
      ),
    )
    await new Promise((resolve) => (worker.onmessage = resolve))
    await new Promise((resolve) => setTimeout(resolve, 200))
  }, ERROR_TOAST)
}

test.describe('the error guard', () => {
  let context: BrowserContext
  let guard: ErrorGuard
  let page: Page

  test.beforeEach(async ({ browser }) => {
    // Not watched by the fixture, which would fail these tests on the errors they cause.
    context = await newUnwatchedContext(browser)
    guard = new ErrorGuard()
    await guard.watch(context)
    await serveApp(context)
    page = await context.newPage()
    await page.goto(`${APP}/app`)
  })

  test.afterEach(async () => {
    await context.close()
  })

  test('reports every error a test did not declare, without query strings', async () => {
    await causeErrors(page)
    const problems = await guard.problems()
    expect(problems).not.toBeNull()
    const lines = problems!.split('\n')
    expect(lines[0]).toBe('8 unexpected error(s) in the browser:')
    expect(lines.at(-1)).toBe('(1 cancelled request(s) not counted)')
    // Events of the page, of its worker and of the network arrive in no fixed order.
    const body = lines.slice(1, -1).map((text) => text.replace(/blob:\S+/, 'blob'))
    expect(body.sort()).toEqual(
      [
        `  toast: Toast text ${APP}/app`,
        // page.evaluate's own script has no URL.
        '  console error: Console text',
        '  vue warning: [Vue warn]: Warning text',
        '  page error: Thrown text',
        '  page error: Rejected text',
        `  response: GET 500 ${APP}/data`,
        `  request failed: GET net::ERR_CONNECTION_REFUSED ${APP}/refused`,
        '  console error: Worker text blob',
      ].sort(),
    )
    expect(problems).not.toMatch(/secret/)
  })

  test('allows declared errors and fails a declaration nothing matched', async () => {
    await causeErrors(page)
    guard.expect({ kind: 'toast', text: /^Toast text$/ })
    guard.expect({ kind: 'console error', text: /^(Console|Worker) text$/ })
    guard.expect({ kind: 'vue warning', text: /Warning text/ })
    guard.expect({ kind: 'page error', text: /^(Thrown|Rejected) text$/ })
    guard.expect({ kind: 'response', status: 500, url: /\/data$/ })
    guard.expect({ kind: 'request failed', url: /\/refused$/ })
    guard.expect({ kind: 'toast', text: /Never shown/ })
    expect(await guard.problems()).toBe(
      [
        '1 declared error(s) never seen:',
        '  toast, text /Never shown/',
        '(1 cancelled request(s) not counted)',
      ].join('\n'),
    )
  })

  test('a declaration is not checked when the test failed already', async () => {
    guard.expect({ kind: 'toast', text: /Never shown/ })
    expect(await guard.problems(true)).toBeNull()
  })

  test('a toast that becomes an error toast by its class alone is reported', async () => {
    await page.evaluate((toastClass) => {
      const toast = document.createElement('div')
      toast.className = 'p-toast-message p-toast-message-info'
      toast.textContent = 'Became an error'
      document.body.append(toast)
      setTimeout(() => toast.classList.replace('p-toast-message-info', toastClass), 50)
    }, ERROR_TOAST)
    // Seen as it changes, not only by the scan at the end.
    await expect.poll(() => guard.recorded.length).toBe(1)
    expect(await guard.problems()).toBe(
      ['1 unexpected error(s) in the browser:', `  toast: Became an error ${APP}/app`].join('\n'),
    )
  })

  test('errors shown in the page are reported; warnings and info notices are not', async () => {
    await page.evaluate(() => {
      document.body.innerHTML = `
        <div data-testid="metric-chart" data-metric-key="train/loss">
          <svg data-testid="chart-error"></svg>
        </div>
        <div data-testid="experiment-status-notice" class="p-message p-message-error">
          Read failed
        </div>
        <div data-testid="experiment-status-notice" class="p-message p-message-warn">Skipped</div>
        <div data-testid="experiment-status-notice" class="p-message p-message-info">Full</div>
        <div class="state-content warning">Too big</div>
        <div class="table-preview"><p><span class="error">Not this one</span></p></div>`
      const later = () => {
        const preview = document.createElement('div')
        preview.className = 'state-content error'
        preview.textContent = 'Preview failed'
        document.body.append(preview)
        const table = document.querySelector('.table-preview')!
        const error = document.createElement('div')
        error.className = 'error'
        error.textContent = 'Table failed'
        table.append(error)
      }
      setTimeout(later, 50)
    })
    await expect.poll(() => guard.recorded.length).toBe(4)
    const problems = await guard.problems()
    const lines = problems!.split('\n')
    expect(lines[0]).toBe('4 unexpected error(s) in the browser:')
    expect(lines.slice(1).sort()).toEqual(
      [
        `  error state: chart train/loss ${APP}/app`,
        `  error state: Read failed ${APP}/app`,
        `  error state: Preview failed ${APP}/app`,
        `  error state: Table failed ${APP}/app`,
      ].sort(),
    )
  })

  test('a request to the internet is reported; the known third parties are answered', async () => {
    // From a blank page: Chromium refuses a page whose document no server sent (the test's route
    // answers APP) access to loopback, where the answers come from.
    const blank = await context.newPage()
    const answers = await blank.evaluate(async () => {
      const read = async (url: string) => {
        try {
          const response = await fetch(url)
          return `${response.status} ${await response.text()}`
        } catch (error) {
          return String(error)
        }
      }
      return [
        await read('https://api.github.com/repos/luml-ai/luml'),
        await read('https://fonts.googleapis.com/css?family=Inter'),
        await read('https://api.github.com/unknown'),
        await read('https://example.org/data?token=secret-token'),
      ]
    })
    expect(answers).toEqual([
      `200 ${THIRD_PARTY[0]!.body}`,
      '200 ',
      '404 not a known third-party call',
      'TypeError: Failed to fetch',
    ])
    const problems = await guard.problems()
    expect(problems!.split('\n').sort()).toEqual(
      [
        '2 unexpected error(s) in the browser:',
        '  response: GET 404 https://api.github.com/unknown',
        '  external request: GET https://example.org/data',
      ].sort(),
    )
    expect(problems).not.toMatch(/secret/)
  })

  test('errors that come after the test body are still reported', async () => {
    // The request is under way when the test ends; its error response comes a second later.
    const sent = page.waitForEvent('request', (request) => request.url().endsWith('/late'))
    await page.evaluate(() => {
      void fetch('/late').catch(() => undefined)
      setTimeout(() => console.error('Late text'))
    })
    await sent
    expect(await guard.problems()).toBe(
      [
        '2 unexpected error(s) in the browser:',
        '  console error: Late text',
        `  response: GET 503 ${APP}/late`,
      ].join('\n'),
    )
  })

  test('a read of a terminated worker that never ends does not hold the end of the test', async () => {
    await page.evaluate(async () => {
      // A blob worker has no base URL for a relative one.
      const source = `fetch('${location.origin}/slow'); postMessage(0)`
      const worker = new Worker(
        URL.createObjectURL(new Blob([source], { type: 'text/javascript' })),
      )
      await new Promise((resolve) => (worker.onmessage = resolve))
      ;(window as unknown as { held: Worker }).held = worker
    })
    await expect.poll(() => page.workers().length).toBe(1)
    const worker = page.workers()[0]!
    const closed = worker.waitForEvent('close')
    await page.evaluate(() => (window as unknown as { held: Worker }).held.terminate())
    await closed
    const started = Date.now()
    expect(await guard.problems()).toBeNull()
    // The guard waits up to 5 s for answers still on the way; this one can never come.
    expect(Date.now() - started).toBeLessThan(2_000)
  })

  test('a late error response of a live worker is still reported', async () => {
    const sent = context.waitForEvent('request', (request) => request.url().endsWith('/late'))
    await page.evaluate(async () => {
      const source = `fetch('${location.origin}/late').catch(() => undefined); postMessage(0)`
      const worker = new Worker(
        URL.createObjectURL(new Blob([source], { type: 'text/javascript' })),
      )
      await new Promise((resolve) => (worker.onmessage = resolve))
      ;(window as unknown as { kept: Worker }).kept = worker
    })
    await sent
    expect(await guard.problems()).toBe(
      ['1 unexpected error(s) in the browser:', `  response: GET 503 ${APP}/late`].join('\n'),
    )
  })

  test("a late error response of the page's own read is still reported when a worker has ended", async () => {
    const sent = context.waitForEvent('request', (request) => request.url().endsWith('/late'))
    await page.evaluate(async () => {
      const worker = new Worker(
        URL.createObjectURL(new Blob(['postMessage(0)'], { type: 'text/javascript' })),
      )
      await new Promise((resolve) => (worker.onmessage = resolve))
      void fetch('/late').catch(() => undefined)
      worker.terminate()
    })
    await sent
    await expect.poll(() => page.workers().length).toBe(0)
    expect(await guard.problems()).toBe(
      ['1 unexpected error(s) in the browser:', `  response: GET 503 ${APP}/late`].join('\n'),
    )
  })

  test('a toast of an earlier document of the page still counts', async () => {
    await page.evaluate((toastClass) => {
      const toast = document.createElement('div')
      toast.className = toastClass
      toast.textContent = 'Before reload'
      document.body.append(toast)
    }, ERROR_TOAST)
    await expect.poll(() => guard.recorded.length).toBe(1)
    await page.reload()
    expect(await guard.problems()).toBe(
      ['1 unexpected error(s) in the browser:', `  toast: Before reload ${APP}/app`].join('\n'),
    )
  })
})

test('redacts signatures, keys, tokens and credentials in message text', () => {
  const probes: [string, string][] = [
    ['GET https://h/x?X-Amz-Signature=s1&a=b', 'GET https://h/x'],
    ['read /blob?sv=1&sig=s2 failed', 'read /blob failed'],
    ['sig=s3&se=2026 expired', 'sig=<redacted>&se=2026 expired'],
    [
      'X-Amz-Credential=s4/2026 X-Amz-Signature=s5',
      'X-Amz-Credential=<redacted> X-Amz-Signature=<redacted>',
    ],
    ['AccountKey=s6==;BlobEndpoint=http://h', 'AccountKey=<redacted>;BlobEndpoint=http://h'],
    ['SharedAccessSignature=s7;x', 'SharedAccessSignature=<redacted>;x'],
    ['signature=s8 Credential=s9', 'signature=<redacted> Credential=<redacted>'],
    ['token=s10 and session-token=s11', 'token=<redacted> and session-token=<redacted>'],
    ['Authorization: Basic s12 sent', 'Authorization: <redacted> sent'],
    ['Authorization: Bearer s13', 'Authorization: <redacted>'],
    ['Bearer s14', 'Bearer <redacted>'],
    ['open http://h/app#session-token=s15', 'open http://h/app'],
  ]
  for (const [text, expected] of probes) expect(redact(text), text).toBe(expected)
  expect(probes.map(([text]) => redact(text)).join(' ')).not.toMatch(/s\d/)
})

// The fixture of every stack test. Expected to fail: a guard that stops failing turns them red.
test.describe('the error guard fixture', () => {
  test('fails a test that leaves an undeclared console error', async ({ page }) => {
    test.fail()
    await serveApp(page.context())
    await page.goto(`${APP}/app`)
    await page.evaluate(() => console.error('Undeclared'))
  })

  test('fails a test whose declared error never came', async ({ page, errors }) => {
    test.fail()
    errors.expect({ kind: 'toast', text: /Never shown/ })
    await serveApp(page.context())
    await page.goto(`${APP}/app`)
  })

  test('fails a test whose own context shows an undeclared error', async ({ browser }) => {
    test.fail()
    const context = await browser.newContext()
    await serveApp(context)
    const page = await context.newPage()
    await page.goto(`${APP}/app`)
    await page.evaluate(() => console.error('In a context of the test'))
    await context.close()
  })

  test('fails a test that asks the internet', async ({ page }) => {
    test.fail()
    await serveApp(page.context())
    await page.goto(`${APP}/app`)
    await page.evaluate(() => fetch('https://example.org/').catch(() => undefined))
  })
})
