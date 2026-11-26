import { afterEach, describe, expect, it, vi } from 'vitest'
import axios, { type AxiosAdapter } from 'axios'
import {
  installInterceptors,
  MONITORING_SESSION_EXPIRED_MESSAGE,
  resetSessionExpiredReport,
} from './api.interceptors'
import { ApiError, SessionExpiredError } from './api.errors'
import { ApiClass, MONITORING_API_BASE } from './api'

const respondWith =
  (status: number): AxiosAdapter =>
  (config) =>
    status < 400
      ? Promise.resolve({ data: {}, status, statusText: '', headers: {}, config })
      : Promise.reject(
          new axios.AxiosError('failed', 'ERR_BAD_RESPONSE', config, null, {
            data: {},
            status,
            statusText: '',
            headers: {},
            config,
          }),
        )

const createInstance = (status: number) => {
  const instance = axios.create({ adapter: respondWith(status) })
  installInterceptors(instance)
  return instance
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('api', () => {
  it('maps 401 to SessionExpiredError', async () => {
    await expect(createInstance(401).get('/header')).rejects.toBeInstanceOf(SessionExpiredError)
  })

  it('notifies the Platform once when the session expires', async () => {
    resetSessionExpiredReport()
    const postMessage = vi.spyOn(window.parent, 'postMessage').mockImplementation(() => {})
    const instance = createInstance(401)
    await instance.get('/header').catch(() => null)
    await instance.get('/runtime').catch(() => null)
    expect(postMessage).toHaveBeenCalledTimes(1)
    expect(postMessage).toHaveBeenCalledWith({ type: MONITORING_SESSION_EXPIRED_MESSAGE }, '*')
  })

  it('maps other failures to ApiError with status', async () => {
    const error = await createInstance(503)
      .get('/header')
      .catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).status).toBe(503)
  })

  it('passes successful responses through', async () => {
    await expect(createInstance(200).get('/header')).resolves.toMatchObject({ status: 200 })
  })

  it('targets the same-origin Satellite monitoring API', () => {
    const client = new ApiClass()
    const http = (client.monitoring as unknown as { api: { defaults: { baseURL: string } } }).api
    expect(http.defaults.baseURL).toBe(MONITORING_API_BASE)
    expect(MONITORING_API_BASE).toBe('/monitoring/api')
  })
})
