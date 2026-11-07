import axios, { AxiosError, type AxiosAdapter, type InternalAxiosRequestConfig } from 'axios'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiClass } from '../api'

function unauthorized(config: InternalAxiosRequestConfig) {
  return Promise.reject(
    new AxiosError('Unauthorized', 'ERR_BAD_REQUEST', config, undefined, {
      config,
      status: 401,
      statusText: 'Unauthorized',
      headers: {},
      data: {},
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
