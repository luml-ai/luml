import type { Page, Route, Request } from '@playwright/test'

export type MockResponse =
  | {
      status?: number
      body?: unknown
      headers?: Record<string, string>
    }
  | unknown 

export type MockHandler = MockResponse | ((req: Request) => MockResponse | Promise<MockResponse>)

const API_BASE = process.env.PLAYWRIGHT_API_BASE ?? '**/api/**'

function normalize(resp: MockResponse): {
  status: number
  body: unknown
  headers: Record<string, string>
} {
  if (resp && typeof resp === 'object') {
    const r = resp as {
      status?: unknown
      body?: unknown
      headers?: unknown
    }
    const looksLikeWrapper =
      typeof r.status === 'number' ||
      (typeof r.headers === 'object' && r.headers !== null) ||
      'body' in r
    if (looksLikeWrapper) {
      return {
        status: typeof r.status === 'number' ? r.status : 200,
        body: r.body ?? {},
        headers: (r.headers as Record<string, string>) ?? {},
      }
    }
  }
  return { status: 200, body: resp, headers: {} }
}

async function register(
  page: Page,
  method: string,
  urlPattern: string | RegExp,
  handler: MockHandler,
) {
  await page.route(urlPattern, async (route: Route, req: Request) => {
    if (req.method() !== method) {
      await route.fallback()
      return
    }
    const resolved = typeof handler === 'function' ? await (handler as Function)(req) : handler
    const { status, body, headers } = normalize(resolved)
    await route.fulfill({
      status,
      headers: { 'content-type': 'application/json', ...headers },
      body: typeof body === 'string' ? body : JSON.stringify(body),
    })
  })
}

export function createApiMocks(page: Page) {
  return {
    get: (url: string | RegExp, handler: MockHandler) => register(page, 'GET', url, handler),
    post: (url: string | RegExp, handler: MockHandler) => register(page, 'POST', url, handler),
    put: (url: string | RegExp, handler: MockHandler) => register(page, 'PUT', url, handler),
    patch: (url: string | RegExp, handler: MockHandler) => register(page, 'PATCH', url, handler),
    delete: (url: string | RegExp, handler: MockHandler) => register(page, 'DELETE', url, handler),

    blockUnmocked: async () => {
      await page.route(API_BASE, async (route: Route) => {
        await route.fulfill({
          status: 599,
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({
            error: 'UNMOCKED_API_CALL',
            url: route.request().url(),
            method: route.request().method(),
          }),
        })
      })
    },
  }
}

export type ApiMocks = ReturnType<typeof createApiMocks>