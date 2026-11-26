import type { AxiosInstance } from 'axios'
import type { QueryParams } from '../api.interfaces'
import type {
  AlertsResponse,
  DataQualityResponse,
  Dimensions,
  FeatureDriftResponse,
  HeaderResponse,
  OutputDriftResponse,
  OverviewResponse,
  ReferenceProfileResponse,
  RuntimeResponse,
  SessionInfo,
  TraceDetailResponse,
  TracesPage,
  TracesResponse,
  WorkerHealthResponse,
} from './interfaces'

export const cleanParams = (params: QueryParams): Record<string, string> =>
  Object.fromEntries(
    Object.entries(params).filter(
      (entry): entry is [string, string] => entry[1] != null && entry[1] !== '',
    ),
  )

export const dimensionParams = (dims: Dimensions): Record<string, string> =>
  cleanParams({
    window: dims.window,
    compare: dims.compare,
    severity: dims.severity,
    granularity: dims.granularity,
    feature: dims.feature,
    start: dims.start,
    end: dims.end,
    compare_start: dims.compareStart,
    compare_end: dims.compareEnd,
  })

export class MonitoringApi {
  private api: AxiosInstance

  constructor(api: AxiosInstance) {
    this.api = api
  }

  async getSessionInfo() {
    const { data } = await this.api.get<SessionInfo>('/session')
    return data
  }

  async getHeader() {
    const { data } = await this.api.get<HeaderResponse>('/header')
    return data
  }

  async getOverview(dims: Dimensions) {
    const { data } = await this.api.get<OverviewResponse>('/overview', {
      params: dimensionParams(dims),
    })
    return data
  }

  async getRuntime(dims: Dimensions) {
    const { data } = await this.api.get<RuntimeResponse>('/runtime', {
      params: dimensionParams(dims),
    })
    return data
  }

  async getDataQuality(dims: Dimensions) {
    const { data } = await this.api.get<DataQualityResponse>('/data-quality', {
      params: dimensionParams(dims),
    })
    return data
  }

  async getFeatureDrift(dims: Dimensions) {
    const { data } = await this.api.get<FeatureDriftResponse>('/feature-drift', {
      params: dimensionParams(dims),
    })
    return data
  }

  async getOutputDrift(dims: Dimensions) {
    const { data } = await this.api.get<OutputDriftResponse>('/output-drift', {
      params: dimensionParams(dims),
    })
    return data
  }

  async getReferenceProfile(dims: Dimensions) {
    const { data } = await this.api.get<ReferenceProfileResponse>('/reference-profile', {
      params: dimensionParams(dims),
    })
    return data
  }

  async getAlerts(dims: Dimensions) {
    const { data } = await this.api.get<AlertsResponse>('/alerts', {
      params: dimensionParams(dims),
    })
    return data
  }

  async acknowledgeAlert(dims: Dimensions, metric: string) {
    const { data } = await this.api.post<AlertsResponse>(
      '/alerts/acknowledge',
      { metric },
      { params: dimensionParams(dims) },
    )
    return data
  }

  async getWorkerHealth() {
    const { data } = await this.api.get<WorkerHealthResponse>('/worker')
    return data
  }

  async getTraces(dims: Dimensions, page: TracesPage) {
    const { data } = await this.api.get<TracesResponse>('/traces', {
      params: cleanParams({
        ...dimensionParams(dims),
        limit: String(page.limit),
        offset: String(page.offset),
        sort: page.sort,
        order: page.order,
      }),
    })
    return data
  }

  async getTraceDetail(dims: Dimensions, eventId: string) {
    const { data } = await this.api.get<TraceDetailResponse>(
      `/traces/${encodeURIComponent(eventId)}`,
      { params: dimensionParams(dims) },
    )
    return data
  }
}
