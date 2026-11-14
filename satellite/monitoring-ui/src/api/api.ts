import axios from 'axios'
import type { AxiosInstance } from 'axios'
import { installInterceptors } from './api.interceptors'
import { mockAdapter } from './api.mock'
import { MonitoringApi } from './monitoring'

export const MONITORING_API_BASE = '/monitoring/api'

export const isApiMockEnabled = () => import.meta.env.VITE_API_MOCK === 'true'

export class ApiClass {
  private api: AxiosInstance
  public monitoring: MonitoringApi

  constructor(useMock = isApiMockEnabled()) {
    this.api = axios.create({
      baseURL: MONITORING_API_BASE,
      timeout: 10000,
      withCredentials: true,
      headers: { Accept: 'application/json' },
      adapter: useMock ? mockAdapter : undefined,
    })

    installInterceptors(this.api)

    this.monitoring = new MonitoringApi(this.api)
  }
}
