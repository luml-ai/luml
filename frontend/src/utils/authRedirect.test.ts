import { beforeEach, describe, expect, it } from 'vitest'
import {
  clearStoredAuthRedirect,
  getSafeAuthRedirect,
  getStoredAuthRedirect,
  storeAuthRedirect,
} from './authRedirect'

describe('auth redirect', () => {
  beforeEach(() => localStorage.clear())

  it('accepts same-origin application paths', () => {
    expect(getSafeAuthRedirect('/invitations?tab=pending#invite')).toBe(
      '/invitations?tab=pending#invite',
    )
  })

  it.each(['https://example.com', '//example.com', 'invitations', null])(
    'rejects unsafe redirect %s',
    (redirect) => {
      expect(getSafeAuthRedirect(redirect)).toBeUndefined()
    },
  )

  it('stores and clears a safe redirect', () => {
    storeAuthRedirect('/invitations')
    expect(getStoredAuthRedirect()).toBe('/invitations')

    clearStoredAuthRedirect()
    expect(getStoredAuthRedirect()).toBeUndefined()
  })

  it('removes an existing redirect when a new value is unsafe', () => {
    storeAuthRedirect('/invitations')
    storeAuthRedirect('https://example.com')

    expect(getStoredAuthRedirect()).toBeUndefined()
  })
})
