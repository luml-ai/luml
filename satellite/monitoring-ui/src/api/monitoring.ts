import { apiGet, type QueryParams } from './client'
import type {
  DataQualityResponse,
  Dimensions,
  FeatureDriftResponse,
  HeaderResponse,
  OverviewResponse,
  ReferenceProfileResponse,
  TraceDetailResponse,
  TracesResponse,
} from './types'

export function dimensionParams(dims: Dimensions): QueryParams {
  return {
    window: dims.window,
    compare: dims.compare,
    severity: dims.severity,
    feature: dims.feature,
  }
}

export function getHeader(): Promise<HeaderResponse> {
  return apiGet<HeaderResponse>('/header')
}

export function getOverview(dims: Dimensions): Promise<OverviewResponse> {
  return apiGet<OverviewResponse>('/overview', dimensionParams(dims))
}

export function getDataQuality(dims: Dimensions): Promise<DataQualityResponse> {
  return apiGet<DataQualityResponse>('/data-quality', dimensionParams(dims))
}

export function getFeatureDrift(dims: Dimensions): Promise<FeatureDriftResponse> {
  return apiGet<FeatureDriftResponse>('/feature-drift', dimensionParams(dims))
}

export function getReferenceProfile(dims: Dimensions): Promise<ReferenceProfileResponse> {
  return apiGet<ReferenceProfileResponse>('/reference-profile', dimensionParams(dims))
}

export function getTraces(
  dims: Dimensions,
  page: { limit: number; offset: number },
): Promise<TracesResponse> {
  return apiGet<TracesResponse>('/traces', {
    ...dimensionParams(dims),
    limit: String(page.limit),
    offset: String(page.offset),
  })
}

/** The window must match the table's: the API looks the event up inside it. */
export function getTraceDetail(dims: Dimensions, eventId: string): Promise<TraceDetailResponse> {
  return apiGet<TraceDetailResponse>(
    `/traces/${encodeURIComponent(eventId)}`,
    dimensionParams(dims),
  )
}
