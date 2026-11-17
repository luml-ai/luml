import { describe, expect, it } from 'vitest'
import { ExperimentSnapshotDatabaseProvider } from '@/providers/ExperimentSnapshotDatabaseProvider'
import { flattenTraceTree, spansWithChildren } from '../traceRows'
import { makeSpan, wideTree } from './spanFactory'

function flatSpan(spanId: string, parent: string | null, start: number) {
  const { children: _children, ...span } = makeSpan(spanId, {
    parent_span_id: parent,
    start_time_unix_nano: start,
    end_time_unix_nano: start + 10,
  })
  return span
}

async function providerTree() {
  // Listed out of start order, with one span whose parent is missing.
  const spans = [
    flatSpan('b', 'root', 30),
    flatSpan('orphan', 'missing', 5),
    flatSpan('a2', 'a', 25),
    flatSpan('root', null, 10),
    flatSpan('a', 'root', 20),
    flatSpan('a1', 'a', 21),
  ]
  return new ExperimentSnapshotDatabaseProvider().buildSpanTree(spans)
}

describe('flattenTraceTree', () => {
  it('lists spans depth first in start order, with orphans as roots', async () => {
    const rows = flattenTraceTree(await providerTree(), new Set())

    expect(rows.map((row) => [row.span.span_id, row.depth])).toEqual([
      ['orphan', 0],
      ['root', 0],
      ['a', 1],
      ['a1', 2],
      ['a2', 2],
      ['b', 1],
    ])
    expect(rows.every((row) => row.opened)).toBe(true)
  })

  it('leaves out the subtree of a collapsed span and marks it closed', async () => {
    const rows = flattenTraceTree(await providerTree(), new Set(['a']))

    expect(rows.map((row) => row.span.span_id)).toEqual(['orphan', 'root', 'a', 'b'])
    expect(rows.find((row) => row.span.span_id === 'a')?.opened).toBe(false)
  })

  it('flattens 10,000 spans', () => {
    const rows = flattenTraceTree(wideTree(99, 100), new Set())

    expect(rows).toHaveLength(10_000)
    expect(rows[1]?.depth).toBe(1)
    expect(rows[2]?.depth).toBe(2)
  })
})

describe('spansWithChildren', () => {
  it('returns only spans that have children', async () => {
    expect(new Set(spansWithChildren(await providerTree()))).toEqual(new Set(['root', 'a']))
  })
})
