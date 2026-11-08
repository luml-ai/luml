import axios, { AxiosError, type AxiosAdapter, type InternalAxiosRequestConfig } from 'axios'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiClass } from '../api'

function unauthorized(
  config: InternalAxiosRequestConfig,
  detail = 'Not authenticated',
  status = 401,
) {
  return Promise.reject(
    new AxiosError('Unauthorized', 'ERR_BAD_REQUEST', config, undefined, {
      config,
      status,
      statusText: 'Unauthorized',
      headers: {},
      data: { detail },
    }),
  )
}

describe('session request interception', () => {
  const requests: string[] = []
  const logout = vi.fn()
  let respond: AxiosAdapter
  let api: ApiClass

  beforeEach(() => {
    requests.length = 0
    respond = unauthorized
    const create = axios.create.bind(axios)
    vi.spyOn(axios, 'create').mockImplementation((config) =>
      create({
        ...config,
        adapter: async (request) => {
          requests.push(`${request.method?.toUpperCase()} ${request.url}`)
          return respond(request)
        },
      }),
    )
    vi.spyOn(console, 'error').mockImplementation(() => {})
    window.addEventListener('auth:logout', logout)
    api = new ApiClass()
  })

  afterEach(() => {
    window.removeEventListener('auth:logout', logout)
    vi.restoreAllMocks()
  })

  it('ends an anonymous session check after one unauthorized request without logout or errors', async () => {
    await expect(api.getMe()).rejects.toMatchObject({ response: { status: 401 } })

    expect(requests).toEqual(['GET /v1/auth/users/me'])
    expect(logout).not.toHaveBeenCalled()
    expect(console.error).not.toHaveBeenCalled()
  })

  it('refreshes a returning session and retries the session check', async () => {
    const user = { id: 'user-id' }
    respond = async (config) => {
      if (requests.length === 1) return unauthorized(config, 'Session refresh required')
      return { config, status: 200, statusText: 'OK', headers: {}, data: user }
    }

    await expect(api.getMe()).resolves.toEqual(user)

    expect(requests).toEqual([
      'GET /v1/auth/users/me',
      'POST /v1/auth/refresh',
      'GET /v1/auth/users/me',
    ])
    expect(logout).not.toHaveBeenCalled()
    expect(console.error).not.toHaveBeenCalled()
  })

  it.each([400, 401, 500])('ends a failed session refresh quietly (%s)', async (status) => {
    respond = (config) =>
      config.url === '/v1/auth/refresh'
        ? unauthorized(config, 'Invalid refresh token', status)
        : unauthorized(config, 'Session refresh required')

    await expect(api.getMe()).rejects.toMatchObject({ response: { status } })

    expect(requests).toEqual(['GET /v1/auth/users/me', 'POST /v1/auth/refresh'])
    expect(logout).not.toHaveBeenCalled()
    expect(console.error).not.toHaveBeenCalled()
  })

  it('does not refresh a session check again when its retry is unauthorized', async () => {
    respond = async (config) => {
      if (config.url !== '/v1/auth/refresh') {
        return unauthorized(config, 'Session refresh required')
      }
      return { config, status: 200, statusText: 'OK', headers: {}, data: {} }
    }

    await expect(api.getMe()).rejects.toMatchObject({ response: { status: 401 } })

    expect(requests).toEqual([
      'GET /v1/auth/users/me',
      'POST /v1/auth/refresh',
      'GET /v1/auth/users/me',
    ])
    expect(logout).not.toHaveBeenCalled()
    expect(console.error).not.toHaveBeenCalled()
  })

  it.each([false, true])(
    'shares a successful refresh with a concurrent protected request (session first: %s)',
    async (sessionFirst) => {
      let finishRefresh!: () => void
      const refreshing = new Promise<void>((resolve) => {
        finishRefresh = resolve
      })
      const attempts = new Map<string, number>()
      respond = async (config) => {
        if (config.url === '/v1/auth/refresh') {
          await refreshing
        } else {
          const attempt = (attempts.get(config.url!) ?? 0) + 1
          attempts.set(config.url!, attempt)
          if (attempt === 1) return unauthorized(config, 'Session refresh required')
        }
        return { config, status: 200, statusText: 'OK', headers: {}, data: {} }
      }
      const results = sessionFirst
        ? [api.getMe(), api.getOrganizations()]
        : [api.getOrganizations(), api.getMe()]
      const settled = Promise.allSettled(results)
      await vi.waitFor(() => expect(requests).toHaveLength(3))
      finishRefresh()

      expect((await settled).every((result) => result.status === 'fulfilled')).toBe(true)
      expect(requests.filter((request) => request === 'POST /v1/auth/refresh')).toHaveLength(1)
      expect(logout).not.toHaveBeenCalled()
    },
  )

  it.each([false, true])(
    'logs out once when concurrent protected requests share a failed session refresh (session first: %s)',
    async (sessionFirst) => {
      let finishRefresh!: () => void
      const refreshing = new Promise<void>((resolve) => {
        finishRefresh = resolve
      })
      respond = async (config) => {
        if (config.url === '/v1/auth/refresh') await refreshing
        return unauthorized(config, 'Session refresh required')
      }
      const results = sessionFirst
        ? [api.getMe(), api.getOrganizations(), api.getOrganizations()]
        : [api.getOrganizations(), api.getMe(), api.getOrganizations()]
      const settled = Promise.allSettled(results)
      await vi.waitFor(() => expect(requests).toHaveLength(4))
      finishRefresh()

      expect((await settled).every((result) => result.status === 'rejected')).toBe(true)
      expect(requests.filter((request) => request === 'POST /v1/auth/refresh')).toHaveLength(1)
      expect(logout).toHaveBeenCalledOnce()
      expect(console.error).toHaveBeenCalledOnce()
    },
  )

  it('does not refresh again when concurrent session retries remain unauthorized', async () => {
    let finishRefresh!: () => void
    const refreshing = new Promise<void>((resolve) => {
      finishRefresh = resolve
    })
    respond = async (config) => {
      if (config.url === '/v1/auth/refresh') {
        await refreshing
        return { config, status: 200, statusText: 'OK', headers: {}, data: {} }
      }
      return unauthorized(config, 'Session refresh required')
    }
    const settled = Promise.allSettled([api.getMe(), api.getMe()])
    await vi.waitFor(() => expect(requests).toHaveLength(3))
    finishRefresh()

    expect((await settled).every((result) => result.status === 'rejected')).toBe(true)
    expect(requests.filter((request) => request === 'POST /v1/auth/refresh')).toHaveLength(1)
    expect(requests.filter((request) => request === 'GET /v1/auth/users/me')).toHaveLength(4)
    expect(logout).not.toHaveBeenCalled()
    expect(console.error).not.toHaveBeenCalled()
  })

  it('does not refresh or dispatch another logout for an unauthorized logout request', async () => {
    await expect(api.logout()).rejects.toMatchObject({ response: { status: 401 } })

    expect(requests).toEqual(['POST /v1/auth/logout'])
    expect(logout).not.toHaveBeenCalled()
    expect(console.error).not.toHaveBeenCalled()
  })

  it('still refreshes and retries an unauthorized protected resource', async () => {
    respond = async (config) => {
      if (requests.length === 1) return unauthorized(config)
      return { config, status: 200, statusText: 'OK', headers: {}, data: [] }
    }

    await expect(api.getOrganizations()).resolves.toEqual([])

    expect(requests).toEqual([
      'GET /v1/users/me/organizations',
      'POST /v1/auth/refresh',
      'GET /v1/users/me/organizations',
    ])
    expect(logout).not.toHaveBeenCalled()
  })

  it('dispatches logout once when a protected resource cannot refresh', async () => {
    await expect(api.getOrganizations()).rejects.toMatchObject({ response: { status: 401 } })

    expect(requests).toEqual(['GET /v1/users/me/organizations', 'POST /v1/auth/refresh'])
    expect(logout).toHaveBeenCalledOnce()
  })
})
