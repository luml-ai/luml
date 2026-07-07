import { apiGet, type QueryParams } from './client'
import type { Dimensions, HeaderResponse, OverviewResponse } from './types'

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
