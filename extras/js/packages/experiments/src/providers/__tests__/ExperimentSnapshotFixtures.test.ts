import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import {
  ExperimentSnapshotDatabaseProvider,
  type ExperimentSnapshotModelSource,
} from '../ExperimentSnapshotDatabaseProvider'
import { readSnapshotTraits, type SnapshotTraits } from '../ExperimentSnapshotTraits'
import type { ModelSnapshot, TraceSpan } from '@/interfaces/interfaces'
import { FIXTURES_DIR, indexTar, memoryTransport } from './helpers/snapshotSources'

// Mirrors findExperimentSnapshotArchiveName in frontend/src/lib/fnnx/FnnxService.ts.
const SNAPSHOT_ARCHIVE_REGEX =
  /meta_artifacts\/dataforce\.studio~c~~c~experiment_snapshot~c~v[12]~~et~~[^/]+\/exp\.db(\.zip)?$|^exp\.db(\.zip)?$/

interface MetricStats {
  count: number
  first_step: number
  last_step: number
  first: number
  last: number
  min: number
  max: number
}

interface StoredMetricPoint {
  step: number
  value: number | 'Infinity' | '-Infinity' | null
  sqlite_type: string
}

interface ExpectedTrace {
  trace_id: string
  span_count: number
  root_span: string
  span_names: string[]
  max_depth: number
  execution_time: number
  linked_evals: string[]
  span_types: Record<string, number>
  status_messages: Record<string, string>
  events: Record<string, unknown[]>
  links: Record<string, unknown[]>
}

interface ExpectedEval {
  inputs: Record<string, unknown>
  outputs: Record<string, unknown>
  refs: Record<string, unknown>
  /** The stored text where `JSON.parse` rejects it (a NaN score), as the viewer returns it. */
  scores: Record<string, number> | string
  metadata: Record<string, unknown>
}

interface ExpectedDataset {
  eval_ids: string[]
  evals: Record<string, ExpectedEval>
  average_scores: Record<string, number>
  /** Keys the viewer's own key scan finds, per column; fixtures before 0.6.0 lack them. */
  column_keys?: Record<string, Record<string, string>>
  linked: { eval_id: string; trace_id: string } | null
}

interface FixtureDescription {
  artifact: string
  snapshot_member: string
  /** Generation 2 fixtures also log the bucket-edge metrics described here. */
  metrics?: { catalog: { key: string }[] }
  expected: {
    static_params: Record<string, unknown>
    metrics: Record<string, MetricStats>
    non_finite_metric: { name: string; stored: StoredMetricPoint[] } | null
    attachments: number
    traces: ExpectedTrace[]
    datasets: Record<string, ExpectedDataset>
    eval_annotations: number
    span_annotations: number
    eval_annotation_rationales: [string, string, string][]
  }
}

const FIXTURE_NAMES = [
  'a_premigration_legacy_indexes',
  'a_premigration_wal_lost',
  'b_premigration',
  'c_sdk_0_1_0',
  'd_sdk_0_5_0',
  'e_baseline_quirk',
  'f_model_sdk_0_5_0',
  'g_raw_sdk_0_5_0',
  'h_raw_model_sdk_0_5_0',
  'o_gen1_edge_sdk_0_5_0',
]
const GENERATION_TWO_FIXTURE_NAMES = [
  'i_gen2_sdk_0_6_0',
  'j_gen2_model_sdk_0_6_0',
  'k_gen2_from_rev2',
]
const ANNOTATED_DATASET = 'qa_set'
const NON_ASCII_SEARCH = '東京'

function readFixture(name: string): { description: FixtureDescription; artifact: Uint8Array } {
  const description = JSON.parse(
    readFileSync(resolve(FIXTURES_DIR, `${name}.json`), 'utf-8'),
  ) as FixtureDescription
  return {
    description,
    artifact: new Uint8Array(readFileSync(resolve(FIXTURES_DIR, `${name}.tar`))),
  }
}

/** Picks the transport from the member name, as the platform loader does. */
function snapshotSource(name: string): ExperimentSnapshotModelSource {
  const { description, artifact } = readFixture(name)
  const fileIndex = indexTar(artifact)
  const archiveName = Object.keys(fileIndex).find((file) => SNAPSHOT_ARCHIVE_REGEX.test(file))
  expect(archiveName).toBe(description.snapshot_member)
  const [offset, size] = fileIndex[archiveName!]!
  if (archiveName!.endsWith('.zip')) {
    return { modelId: name, buffer: artifact.slice(offset, offset + size).buffer }
  }
  return { modelId: name, source: { kind: 'range', url: `fixture:${name}`, offset, size } }
}

async function providerForFixtures(names: string[]): Promise<ExperimentSnapshotDatabaseProvider> {
  const { transport } = memoryTransport(
    Object.fromEntries(names.map((name) => [`fixture:${name}`, readFixture(name).artifact])),
  )
  const provider = new ExperimentSnapshotDatabaseProvider({ transport })
  await provider.init({ modelsInfo: names.map(snapshotSource) })
  return provider
}

function treeDepth(spans: TraceSpan[]): number {
  return spans.reduce((depth, span) => Math.max(depth, 1 + treeDepth(span.children)), 0)
}

function annotationTotal(summary: {
  feedback: { total: number }[]
  expectations: { total: number }[]
}): number {
  return [...summary.feedback, ...summary.expectations].reduce((sum, item) => sum + item.total, 0)
}

function storedNumber(value: StoredMetricPoint['value']): number | null {
  if (value === 'Infinity') return Infinity
  if (value === '-Infinity') return -Infinity
  return value
}

function columnNames(dataset: ExpectedDataset, column: keyof ExpectedEval): string[] {
  const keys = dataset.column_keys?.[column]
  if (keys) return Object.keys(keys).sort()
  return [
    ...new Set(Object.values(dataset.evals).flatMap((item) => Object.keys(item[column]))),
  ].sort()
}

const evalParams = (datasetId: string) => ({
  limit: 10,
  sort_by: 'created_at' as const,
  order: 'asc' as const,
  dataset_id: datasetId,
  search: '',
  filters: [],
})

const traceParams = {
  limit: 10,
  sort_by: 'created_at' as const,
  order: 'desc' as const,
  search: '',
  filters: [],
}

describe.each([...FIXTURE_NAMES, ...GENERATION_TWO_FIXTURE_NAMES])(
  'published experiment snapshot fixture %s',
  (name) => {
    const { description } = readFixture(name)
    const expected = description.expected
    const datasets = Object.entries(expected.datasets)
    const annotatedDataset = expected.datasets[ANNOTATED_DATASET]

    it('returns the logged metrics, non-finite values and static params', async () => {
      const provider = await providerForFixtures([name])
      const nonFinite = expected.non_finite_metric

      const bucketEdgeMetrics = description.metrics?.catalog.map((entry) => entry.key) ?? []
      expect((await provider.getDynamicMetricsNames()).sort()).toEqual(
        [
          ...new Set([
            ...Object.keys(expected.metrics),
            ...(nonFinite ? [nonFinite.name] : []),
            ...bucketEdgeMetrics,
          ]),
        ].sort(),
      )
      for (const [metricName, stats] of Object.entries(expected.metrics)) {
        const [metric] = await provider.getDynamicMetricData(metricName)
        expect(metric).toMatchObject({ modelId: name, aggregated: false })
        expect(metric!.x).toHaveLength(stats.count)
        expect([metric!.x[0], metric!.x.at(-1)]).toEqual([stats.first_step, stats.last_step])
        expect([metric!.y[0], metric!.y.at(-1)]).toEqual([stats.first, stats.last])
        expect([Math.min(...metric!.y), Math.max(...metric!.y)]).toEqual([stats.min, stats.max])
      }
      if (nonFinite) {
        const plotted = nonFinite.stored.filter((point) => point.value !== null)
        const [metric] = await provider.getDynamicMetricData(nonFinite.name)
        expect(metric!.x).toEqual(plotted.map((point) => point.step))
        expect(metric!.y).toEqual(plotted.map((point) => storedNumber(point.value)))
      }
      expect(await provider.getStaticParamsList()).toEqual([
        { ...expected.static_params, modelId: name },
      ])
    })

    it('returns evals, scores, columns and eval annotations for every dataset', async () => {
      const provider = await providerForFixtures([name])

      expect((await provider.getUniqueDatasetsIds()).sort()).toEqual(
        Object.keys(expected.datasets).sort(),
      )
      let annotationsInDatasets = 0
      for (const [datasetId, dataset] of datasets) {
        const evals = await provider.getAllDatasetEvals(evalParams(datasetId))
        expect(evals.map((item) => item.id).sort()).toEqual([...dataset.eval_ids].sort())
        for (const item of evals) {
          expect(item).toMatchObject({ ...dataset.evals[item.id], modelId: name })
        }
        const nextPage = await provider.getNextEvalsByDatasetId(evalParams(datasetId))
        expect(nextPage.map((item) => item.id).sort()).toEqual([...dataset.eval_ids].sort())
        const freshPage = await provider.getFreshEvalsByDatasetId(evalParams(datasetId))
        expect(freshPage.map((item) => item.id).sort()).toEqual([...dataset.eval_ids].sort())
        await provider.resetDatasetPage(datasetId)
        const batch = await provider.getBatchExperimentEvals({
          experiment_ids: [name],
          dataset_id: datasetId,
        })
        expect(batch.items.map((item) => item.id)).toEqual([...dataset.eval_ids].sort())
        expect(batch.cursor).toBeNull()

        const [averages] = await provider.getDatasetAverageScores(datasetId)
        expect(averages!.modelId).toBe(name)
        expect(averages!.scores.map((score) => score.name).sort()).toEqual(
          Object.keys(dataset.average_scores).sort(),
        )
        for (const score of averages!.scores) {
          expect(score.value).toBeCloseTo(dataset.average_scores[score.name]!)
        }

        const perEvalAnnotations = await Promise.all(
          dataset.eval_ids.map((evalId) => provider.getEvalAnnotations(name, datasetId, evalId)),
        )
        const summaryTotal = annotationTotal(
          await provider.getEvalsDatasetAnnotationsSummary(datasetId),
        )
        expect(perEvalAnnotations.flat()).toHaveLength(summaryTotal)
        annotationsInDatasets += summaryTotal
        for (const evalId of dataset.eval_ids) {
          expect(await provider.getEvalById(name, evalId)).toMatchObject({
            id: evalId,
            dataset_id: datasetId,
          })
        }

        const columns = await provider.getEvalsColumns(datasetId)
        for (const column of ['inputs', 'outputs', 'scores'] as const) {
          expect(columns[column].map((item) => item.name).sort()).toEqual(
            columnNames(dataset, column),
          )
        }
      }
      await provider.resetEvalsDatasetsRequestParams()
      expect(annotationsInDatasets).toBe(expected.eval_annotations)

      for (const [evalId, annotationName, rationale] of expected.eval_annotation_rationales) {
        const annotations = await provider.getEvalAnnotations(name, ANNOTATED_DATASET, evalId)
        expect(annotations.find((item) => item.name === annotationName)?.rationale).toBe(rationale)
      }
      if (annotatedDataset) {
        const columns = await provider.getEvalsColumns(ANNOTATED_DATASET)
        expect(columns.annotations_feedback.length > 0).toBe(expected.eval_annotations > 0)
      }
    })

    it('finds non-ASCII eval text by search and by filter', async () => {
      const provider = await providerForFixtures([name])
      const match = Object.entries(annotatedDataset?.evals ?? {}).find(([, item]) =>
        String(item.inputs.question).includes(NON_ASCII_SEARCH),
      )
      const expectedIds = match ? [match[0]] : []

      const searched = await provider.getAllDatasetEvals({
        ...evalParams(ANNOTATED_DATASET),
        search: NON_ASCII_SEARCH,
      })
      expect(searched.map((item) => item.id)).toEqual(expectedIds)
      const filters = [`inputs.question = "${match?.[1].inputs.question ?? NON_ASCII_SEARCH}"`]
      const filtered = await provider.getAllDatasetEvals({
        ...evalParams(ANNOTATED_DATASET),
        filters,
      })
      expect(filtered.map((item) => item.id)).toEqual(expectedIds)
    })

    it('applies annotation filters to evals without failing', async () => {
      const provider = await providerForFixtures([name])
      const filters = ['annotations.helpful = "true"']
      const expectedIds = expected.eval_annotations ? ['e1'] : []

      expect(await provider.validateEvalsFilter(filters)).toEqual([{ valid: true, error: null }])
      const filtered = await provider.getAllDatasetEvals({
        ...evalParams(ANNOTATED_DATASET),
        filters,
      })
      expect(filtered.map((item) => item.id)).toEqual(expectedIds)
      const [averages] = await provider.getDatasetAverageScores(ANNOTATED_DATASET, '', filters)
      expect(averages!.scores.length > 0).toBe(expected.eval_annotations > 0)
      const batch = await provider.getBatchExperimentEvals({
        dataset_id: ANNOTATED_DATASET,
        filters,
      })
      expect(batch.items.map((item) => item.id)).toEqual(expectedIds)
    })

    it('returns traces, span trees, span details, eval links and span annotations', async () => {
      const provider = await providerForFixtures([name])
      const expectedTraceIds = expected.traces.map((trace) => trace.trace_id).sort()

      expect((await provider.getTraces(traceParams)).map((trace) => trace.trace_id).sort()).toEqual(
        expectedTraceIds,
      )
      expect(
        (await provider.getFreshTraces(traceParams)).map((trace) => trace.trace_id).sort(),
      ).toEqual(expectedTraceIds)
      await provider.resetTracesRequestParams(name)
      await provider.resetTracesRequestParams()
      const traces = await provider.getAllTraces(traceParams)
      expect(traces).toHaveLength(expected.traces.length)

      let annotationsInTraces = 0
      let annotationsOnSpans = 0
      for (const expectedTrace of expected.traces) {
        const trace = traces.find((item) => item.trace_id === expectedTrace.trace_id)!
        expect(trace).toMatchObject({
          span_count: expectedTrace.span_count,
          execution_time: expectedTrace.execution_time,
          evals: expectedTrace.linked_evals,
        })
        annotationsInTraces += annotationTotal(trace.annotations)

        const spans = (await provider.getTraceSpans(name, expectedTrace.trace_id))!
        expect(spans.map((span) => span.name).sort()).toEqual(expectedTrace.span_names)
        for (const span of spans) {
          expect(span.dfs_span_type).toBe(expectedTrace.span_types[span.span_id])
          annotationsOnSpans += span.annotation_count ?? 0
          // Revision 3 snapshots return the tree without payloads; each span loads its own.
          expect(span.payloadLoaded).toBe(!GENERATION_TWO_FIXTURE_NAMES.includes(name))
          const payload = await provider.getSpanPayload(name, span.trace_id, span.span_id)
          if (span.payloadLoaded) {
            expect(payload).toEqual({
              attributes: span.attributes,
              events: span.events,
              links: span.links,
              status_message: span.status_message,
            })
          } else {
            expect([span.attributes, span.events, span.links, span.status_message]).toEqual([
              null,
              null,
              null,
              null,
            ])
          }
          expect(payload.status_message).toBe(expectedTrace.status_messages[span.span_id] ?? null)
          expect(payload.events).toEqual(expectedTrace.events[span.span_id] ?? null)
          expect(payload.links).toEqual(expectedTrace.links[span.span_id] ?? null)
        }
        const tree = await provider.buildSpanTree(spans)
        expect(tree.map((span) => span.name)).toEqual([expectedTrace.root_span])
        expect(treeDepth(tree)).toBe(expectedTrace.max_depth)

        const spanAnnotations = await Promise.all(
          spans.map((span) => provider.getSpanAnnotations(name, span.trace_id, span.span_id)),
        )
        expect(spanAnnotations.flat()).toHaveLength(
          spans.reduce((sum, span) => sum + (span.annotation_count ?? 0), 0),
        )
      }
      expect(annotationsInTraces).toBe(expected.span_annotations)
      expect(annotationsOnSpans).toBe(expected.span_annotations)

      for (const [datasetId, dataset] of datasets) {
        expect(
          await provider.getTraceId({
            modelId: name,
            datasetId,
            evalId: dataset.linked?.eval_id ?? dataset.eval_ids[0]!,
          }),
        ).toBe(dataset.linked?.trace_id ?? null)
      }
      expect(annotationTotal(await provider.getTracesAnnotationSummary(name))).toBe(
        expected.span_annotations,
      )
      const columns = await provider.getTracesColumns(name)
      if (expected.traces.length) {
        expect(columns.attributes.map((column) => column.name)).toEqual(
          expect.arrayContaining(['gen_ai.request.model', 'user.city']),
        )
      }
      expect(columns.annotations_feedback.length > 0).toBe(expected.span_annotations > 0)
    })

    it('applies annotation filters to traces without failing', async () => {
      const provider = await providerForFixtures([name])
      const filters = ['annotations.correct = "true"']

      expect(await provider.validateTracesFilter(filters)).toEqual([{ valid: true, error: null }])
      const traces = await provider.getAllTraces({ ...traceParams, filters })
      expect(traces.map((trace) => trace.trace_id)).toEqual(
        expected.span_annotations ? [expected.traces[0]!.trace_id] : [],
      )
    })
  },
)

describe('comparing published snapshots of different eras', () => {
  const names = [
    'a_premigration_legacy_indexes',
    'd_sdk_0_5_0',
    'a_premigration_wal_lost',
    'e_baseline_quirk',
  ]
  const [oldest, newest, walLost, quirk] = names as [string, string, string, string]
  const expectedOf = (name: string) => readFixture(name).description.expected

  it('returns metrics, evals and traces for every snapshot in one provider', async () => {
    const provider = await providerForFixtures(names)
    const withData = [oldest, newest, quirk]

    expect((await provider.getDynamicMetricsNames()).sort()).toEqual(
      [...Object.keys(expectedOf(newest).metrics), 'unstable_loss'].sort(),
    )
    const lossSeries = await provider.getDynamicMetricData('train_loss')
    expect(lossSeries.map((series) => [series.modelId, series.x.length])).toEqual(
      names.map((name) => [name, expectedOf(name).metrics.train_loss?.count ?? 0]),
    )
    expect(await provider.getStaticParamsList()).toEqual(
      names.map((name) => ({ ...expectedOf(name).static_params, modelId: name })),
    )

    const qaIds = expectedOf(newest).datasets[ANNOTATED_DATASET]!.eval_ids
    const batch = await provider.getBatchExperimentEvals({ dataset_id: ANNOTATED_DATASET })
    expect(batch.items.map((item) => [item.id, item.modelId])).toEqual(
      qaIds.flatMap((id) => [...withData].sort().map((name) => [id, name])),
    )
    const nextPage = await provider.getNextEvalsByDatasetId(evalParams(ANNOTATED_DATASET))
    expect(nextPage).toHaveLength(qaIds.length * withData.length)
    expect(
      annotationTotal(await provider.getEvalsDatasetAnnotationsSummary(ANNOTATED_DATASET)),
    ).toBe(expectedOf(newest).eval_annotations)
    expect(
      (await provider.getDatasetAverageScores(ANNOTATED_DATASET)).map((scores) => [
        scores.modelId,
        scores.scores.length,
      ]),
    ).toEqual(names.map((name) => [name, name === walLost ? 0 : 2]))
    const annotated = await provider.getAllDatasetEvals({
      ...evalParams(ANNOTATED_DATASET),
      filters: ['annotations.helpful = "true"'],
    })
    expect(annotated.map((item) => [item.id, item.modelId])).toEqual([['e1', newest]])
    await expect(provider.getEvalById(walLost, 'e1')).rejects.toThrow('Eval not found')

    const traces = await provider.getAllTraces(traceParams)
    expect(traces).toHaveLength(withData.length * expectedOf(newest).traces.length)
    const annotatedTraces = await provider.getAllTraces({
      ...traceParams,
      filters: ['annotations.correct = "true"'],
    })
    expect(annotatedTraces.map((trace) => trace.trace_id)).toEqual([
      expectedOf(newest).traces[0]!.trace_id,
    ])
    expect(annotationTotal(await provider.getTracesAnnotationSummary(quirk))).toBe(0)
    expect(await provider.getTraceSpans(walLost, expectedOf(newest).traces[0]!.trace_id)).toEqual(
      [],
    )
  })
})

describe('comparing snapshots read through different transports', () => {
  const zipped = 'd_sdk_0_5_0'
  const raw = 'g_raw_sdk_0_5_0'

  it('returns the same data for a zipped and a range-read copy of one experiment', async () => {
    const provider = await providerForFixtures([zipped, raw])

    const [zippedSeries, rawSeries] = await provider.getDynamicMetricData('train_loss')
    expect(rawSeries).toEqual({ ...zippedSeries, modelId: raw })
    const [zippedParams, rawParams] = await provider.getStaticParamsList()
    expect(rawParams).toEqual({ ...zippedParams, modelId: raw })
    const qa = await provider.getBatchExperimentEvals({ dataset_id: ANNOTATED_DATASET })
    const evalsOf = (modelId: string) =>
      qa.items.filter((item) => item.modelId === modelId).map((item) => ({ ...item, modelId: '' }))
    expect(evalsOf(raw)).toEqual(evalsOf(zipped))
    expect(evalsOf(raw).length).toBeGreaterThan(0)
    expect(await provider.getTransportStats()).toEqual([
      expect.objectContaining({ modelId: zipped, transport: 'zip-full', requests: 0 }),
      expect.objectContaining({ modelId: raw, transport: 'raw-range' }),
    ])
  })
})

describe('schema traits of published snapshot fixtures', () => {
  const premigration = {
    revision: 0,
    hasExperimentTables: true,
    hasEvalAnnotations: false,
    hasSpanAnnotations: false,
  }
  const revision2 = {
    revision: 2,
    hasExperimentTables: true,
    hasEvalAnnotations: true,
    hasSpanAnnotations: true,
  }
  const releasedRevisionTraits = {
    unknownNewerRevision: false,
    minReaderRevision: 0,
    needsNewerReader: false,
    metricLayout: 'dynamic-metrics',
    bucketLevels: null,
    structuralTraces: false,
    hasTraceSummaries: false,
    hasScoreStats: false,
    hasKeyCatalogs: false,
  } as const
  const expectedTraits: Record<
    string,
    Omit<SnapshotTraits, keyof typeof releasedRevisionTraits>
  > = {
    a_premigration_legacy_indexes: premigration,
    a_premigration_wal_lost: { ...premigration, hasExperimentTables: false },
    b_premigration: premigration,
    c_sdk_0_1_0: revision2,
    d_sdk_0_5_0: revision2,
    e_baseline_quirk: { ...revision2, hasEvalAnnotations: false, hasSpanAnnotations: false },
    f_model_sdk_0_5_0: revision2,
    g_raw_sdk_0_5_0: revision2,
    h_raw_model_sdk_0_5_0: revision2,
    o_gen1_edge_sdk_0_5_0: revision2,
  }

  it.each(FIXTURE_NAMES)('%s', async (name) => {
    const provider = await providerForFixtures([name])
    const [snapshot] = (provider as unknown as { _modelsSnapshots: ModelSnapshot[] })
      ._modelsSnapshots

    expect(readSnapshotTraits(snapshot!.database)).toEqual({
      ...expectedTraits[name],
      ...releasedRevisionTraits,
    })
  })

  it.each(GENERATION_TWO_FIXTURE_NAMES)('%s', async (name) => {
    const provider = await providerForFixtures([name])
    const [snapshot] = (provider as unknown as { _modelsSnapshots: ModelSnapshot[] })
      ._modelsSnapshots

    expect(readSnapshotTraits(snapshot!.database)).toEqual({
      ...revision2,
      revision: 3,
      unknownNewerRevision: false,
      minReaderRevision: 2,
      needsNewerReader: false,
      metricLayout: 'metric-points',
      bucketLevels: { min: 3, max: 12 },
      structuralTraces: true,
      hasTraceSummaries: true,
      hasScoreStats: true,
      hasKeyCatalogs: true,
    })
  })
})
