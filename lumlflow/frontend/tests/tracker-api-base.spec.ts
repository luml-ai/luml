/**
 * Where the Experiments half sends its calls.
 *
 * Every tracker call is written unprefixed — `/groups`, `/experiments/:id` —
 * so the axios base is the whole address. Left undefined it became the app's
 * own origin with no `/api`, which the SPA fallback answers with index.html:
 * the page then read `items` off an HTML string. The base has a default for
 * exactly that reason, and this is the spec that keeps it.
 *
 * The dev server is its own case: it proxies `/api` to the daemon, so a local
 * `.env` pointing `VITE_API_URL` at some other port must not send the tracker
 * calls past that proxy. Vitest runs in dev mode, which is what lets this spec
 * say so without unsetting anybody's `.env`.
 */

import { describe, expect, it } from 'vitest'
import { api, API_BASE_URL } from '@/api/client'

describe('the tracker API base', () => {
  it('defaults to this origin’s /api rather than to nothing', () => {
    expect(API_BASE_URL).toBe('/api')
    expect(api.defaults.baseURL).toBe('/api')
  })

  it('stays on the dev proxy whatever a local VITE_API_URL says', () => {
    expect(import.meta.env.DEV).toBe(true)
    expect(API_BASE_URL).toBe('/api')
  })

  it('puts the unprefixed paths the call sites use under it', () => {
    expect(new URL(`${API_BASE_URL}/groups`, 'http://127.0.0.1:5000').pathname).toBe('/api/groups')
  })
})
