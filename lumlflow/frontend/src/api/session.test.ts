import { describe, expect, it, vi } from 'vitest'

describe('launch URL pasted into an open tab', () => {
  it('stores the session token, clears the fragment and reloads', async () => {
    localStorage.clear()
    window.history.replaceState(null, '', '/experiments')
    await import('./client')
    const { page } = await import('./session')
    const reload = vi.spyOn(page, 'reload').mockImplementation(() => {})
    window.history.replaceState(null, '', '/experiments#session-token=pasted-session')
    window.dispatchEvent(new HashChangeEvent('hashchange'))
    expect(localStorage.getItem('flow-session-token')).toBe('pasted-session')
    expect(window.location.hash).toBe('')
    expect(reload).toHaveBeenCalledOnce()
  })
})
