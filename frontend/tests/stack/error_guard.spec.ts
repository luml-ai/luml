import type { BrowserContext, Page } from '@playwright/test'
import { ErrorGuard, ERROR_TOAST, expect, test } from './error_guard'

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
    context = await browser.newContext()
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
})
