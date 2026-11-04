
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
