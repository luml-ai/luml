import { apiGet, apiPost, type QueryParams } from './client'
import type {
  SortOrder,
  TraceSortKey,
  AlertsResponse,
  DataQualityResponse,
  Dimensions,
  FeatureDriftResponse,
  HeaderResponse,
  OutputDriftResponse,
  OverviewResponse,
  ReferenceProfileResponse,
  RuntimeResponse,
  TraceDetailResponse,
  TracesResponse,
  WorkerHealthResponse,
} from './types'

export function dimensionParams(dims: Dimensions): QueryParams {
  return {
    window: dims.window,
    compare: dims.compare,
    severity: dims.severity,
    granularity: dims.granularity,
    feature: dims.feature,
    start: dims.start,
    end: dims.end,
    compare_start: dims.compareStart,
    compare_end: dims.compareEnd,
  }
}

export function getSessionInfo(): Promise<{ deployment_id: string; scope: string }> {
  return apiGet('/session')
}

export function getHeader(): Promise<HeaderResponse> {
  return apiGet<HeaderResponse>('/header')
}

export function getOverview(dims: Dimensions): Promise<OverviewResponse> {
  return apiGet<OverviewResponse>('/overview', dimensionParams(dims))
}

export function getRuntime(dims: Dimensions): Promise<RuntimeResponse> {
  return apiGet<RuntimeResponse>('/runtime', dimensionParams(dims))
}

export function getDataQuality(dims: Dimensions): Promise<DataQualityResponse> {
  return apiGet<DataQualityResponse>('/data-quality', dimensionParams(dims))
}

export function getFeatureDrift(dims: Dimensions): Promise<FeatureDriftResponse> {
  return apiGet<FeatureDriftResponse>('/feature-drift', dimensionParams(dims))
}

export function getOutputDrift(dims: Dimensions): Promise<OutputDriftResponse> {
  return apiGet<OutputDriftResponse>('/output-drift', dimensionParams(dims))
}

export function getReferenceProfile(dims: Dimensions): Promise<ReferenceProfileResponse> {
  return apiGet<ReferenceProfileResponse>('/reference-profile', dimensionParams(dims))
}

export function getAlerts(dims: Dimensions): Promise<AlertsResponse> {
  return apiGet<AlertsResponse>('/alerts', dimensionParams(dims))
}

export function acknowledgeAlert(dims: Dimensions, metric: string): Promise<AlertsResponse> {
  return apiPost<AlertsResponse>('/alerts/acknowledge', { metric }, dimensionParams(dims))
}

export function getWorkerHealth(): Promise<WorkerHealthResponse> {
  return apiGet<WorkerHealthResponse>('/worker')
}

export function getTraces(
  dims: Dimensions,
  page: { limit: number; offset: number; sort?: TraceSortKey; order?: SortOrder },
): Promise<TracesResponse> {
  return apiGet<TracesResponse>('/traces', {
    ...dimensionParams(dims),
    limit: String(page.limit),
    offset: String(page.offset),
    sort: page.sort ?? null,
    order: page.order ?? null,
  })
}

/** The window must match the table's: the API looks the event up inside it. */
export function getTraceDetail(dims: Dimensions, eventId: string): Promise<TraceDetailResponse> {
  return apiGet<TraceDetailResponse>(
    `/traces/${encodeURIComponent(eventId)}`,
    dimensionParams(dims),
  )
}
