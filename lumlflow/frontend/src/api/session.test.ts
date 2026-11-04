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

describe('tokenFromLaunchInput', () => {
  it.each([
    ['http://127.0.0.1:5000/#session-token=abc_123', 'abc_123'],
    ['  http://localhost:5065/experiments#session-token=abc  ', 'abc'],
    ['#session-token=abc', 'abc'],
    ['abc_123-XYZ', 'abc_123-XYZ'],
  ])('takes the token from %s', async (input, token) => {
    const { tokenFromLaunchInput } = await import('./session')
    expect(tokenFromLaunchInput(input)).toBe(token)
  })

  it.each(['', '   ', 'http://127.0.0.1:5000/', 'http://127.0.0.1:5000/#other=1', 'two words'])(
    'finds no token in %j',
    async (input) => {
      const { tokenFromLaunchInput } = await import('./session')
      expect(tokenFromLaunchInput(input)).toBeNull()
    },
  )
})
