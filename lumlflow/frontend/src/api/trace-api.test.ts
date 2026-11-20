import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import type { AxiosAdapter, InternalAxiosRequestConfig } from 'axios'
import { ExperimentSnapshotApiProvider } from '@luml/experiments'
import { api } from './client'
import { apiService } from './api.service'
import type { Span } from '@/store/experiments/experiments.interface'

const fullSpan: Span = {
  span_id: 's1',
  parent_span_id: null,
  name: 'chat',
  kind: 0,
  dfs_span_type: 1,
  start_time_unix_nano: 1,
  end_time_unix_nano: 2,
  status_code: 2,
  status_message: 'boom',
  attributes: { model: 'gpt-4o' },
  events: null,
  links: null,
  trace_flags: 1,
  annotation_count: 0,
}

const structureSpan: Span = {
  ...fullSpan,
  status_message: null,
  attributes: null,
  events: null,
  links: null,
}

const requestedUrls: string[] = []

// Answers like the Flow server: `?payloads=false` gives the structure, `/spans/{id}` one span.
const traceServer: AxiosAdapter = async (config: InternalAxiosRequestConfig) => {
  const url = api.getUri(config)
  requestedUrls.push(url)
  const bodies: Record<string, unknown> = {
    '/api/experiments/e1/traces/t1': { trace_id: 't1', spans: [fullSpan] },
    '/api/experiments/e1/traces/t1?payloads=false': { trace_id: 't1', spans: [structureSpan] },
    '/api/experiments/e1/traces/t1/spans/s1': fullSpan,
  }
  if (!(url in bodies)) throw new Error(`Unexpected request ${url}`)
  return { data: bodies[url], status: 200, statusText: '200', headers: {}, config }
}

describe('trace transport', () => {
  const realAdapter = api.defaults.adapter

  beforeEach(() => {
    requestedUrls.length = 0
    api.defaults.adapter = traceServer
  })

  afterEach(() => {
    api.defaults.adapter = realAdapter
  })

  it('requests full spans by default', async () => {
    expect(await apiService.getTraceDetails('e1', 't1')).toEqual({
      trace_id: 't1',
      spans: [fullSpan],
    })
    expect(requestedUrls).toEqual(['/api/experiments/e1/traces/t1'])
  })

  it('requests the structure with payloads=false', async () => {
    const details = await apiService.getTraceDetails('e1', 't1', { payloads: false })

    expect(details.spans).toEqual([structureSpan])
    expect(requestedUrls).toEqual(['/api/experiments/e1/traces/t1?payloads=false'])
  })

  it('requests one span', async () => {
    expect(await apiService.getSpan('e1', 't1', 's1')).toEqual(fullSpan)
    expect(requestedUrls).toEqual(['/api/experiments/e1/traces/t1/spans/s1'])
  })

  it('makes the viewer load the tree without payloads and one span on demand', async () => {
    const provider = new ExperimentSnapshotApiProvider(apiService)
    await provider.init({ artifacts: [{ id: 'e1', dynamicMetrics: [], staticParams: {} }] })

    const spans = await provider.getTraceSpans('e1', 't1')
    expect(spans).toMatchObject([{ span_id: 's1', payloadLoaded: false, attributes: '' }])
    expect(await provider.getSpanPayload('e1', 't1', 's1')).toEqual({
      attributes: JSON.stringify({ model: 'gpt-4o' }),
      events: '',
      links: '',
      status_message: 'boom',
    })
    expect(requestedUrls).toEqual([
      '/api/experiments/e1/traces/t1?payloads=false',
      '/api/experiments/e1/traces/t1/spans/s1',
    ])
  })
})
