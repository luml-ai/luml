import { describe, expect, it } from 'vitest'

import {
  branches,
  cellsByBranch,
  churnFixture,
  mainCells,
  trainModel,
} from '@/flow/workbench/fixtures'
import { formatBytes, formatCost, formatMetric } from '@/flow/workbench/model/format'
import {
  primaryOutput,
  producerOf,
  rankOf,
  reorderNeighbours,
  sliceEdges,
  topologicalOrder,
} from '@/flow/workbench/model/registry'
import type { AssetKind, FlowCell } from '@/flow/workbench/model/types'

/** A cell carrying only what the notebook's order reads: wiring and effective key. */
function authoredCell(slug: string, authoredStep: number, ...consumes: string[]): FlowCell {
  return {
    slug,
    doc: '',
    consumes,
    params: {},
    source: '',
    outputs: [],
    status: 'materialized',
    authoredStep,
    order: String(authoredStep),
  }
}

describe('primary output ranking', () => {
  it('opens a training cell on the experiment, not the model or a config dump', () => {
    expect(primaryOutput(trainModel)?.name).toBe('run')
  })

  it('honors an explicit primaryOutput over the ranking', () => {
    const cell = { ...trainModel, primaryOutput: 'curves' }
    expect(primaryOutput(cell)?.name).toBe('curves')
  })

  it('falls back to the ranking when the declared primary is missing', () => {
    const cell = { ...trainModel, primaryOutput: 'nonexistent' }
    expect(primaryOutput(cell)?.name).toBe('run')
  })

  it('ranks experiment above eval above plot above frame', () => {
    expect(rankOf('experiment')).toBeLessThan(rankOf('eval'))
    expect(rankOf('eval')).toBeLessThan(rankOf('plot'))
    expect(rankOf('plot')).toBeLessThan(rankOf('frame'))
  })

  // The daemon names the primary output; this order only decides when it has
  // not, so it has to be the same order — `_KIND_ORDER` in daemon/queries.py.
  it('reads in the one documented order, with unlisted kinds last', () => {
    const documented: AssetKind[] = [
      'experiment',
      'eval',
      'plot',
      'frame',
      'note',
      'metric',
      'dataset',
      'model',
      'file',
      'checkpoint',
      'unknown',
    ]
    const ranks = documented.map(rankOf)
    expect(ranks).toEqual([...ranks].sort((a, b) => a - b))
    expect(new Set(ranks).size).toBe(documented.length)

    // An attachment kind is not in the daemon's vocabulary; it sorts after the
    // kinds that are, rather than ahead of the checkpoint beside it.
    for (const unlisted of ['image', 'html', 'text'] as AssetKind[]) {
      expect(rankOf(unlisted)).toBeGreaterThan(rankOf('unknown'))
    }
  })

  it('opens a metric-shaped summary ahead of a dataset it ships beside', () => {
    const cell: FlowCell = {
      ...trainModel,
      primaryOutput: undefined,
      outputs: [
        {
          name: 'clean',
          declared: 'dataset',
          kind: 'dataset',
          preview: { type: 'kv', entries: {} },
        },
        {
          name: 'summary',
          declared: 'asset',
          kind: 'metric',
          preview: { type: 'kv', entries: {} },
        },
      ],
    }
    expect(primaryOutput(cell)?.name).toBe('summary')
  })
})

describe('slice wiring', () => {
  it('derives edges from declared consumes references', () => {
    const edges = sliceEdges(mainCells)
    expect(edges).toContainEqual({ from: 'features', to: 'train_model', input: '0' })
    expect(edges).toContainEqual({ from: 'train_model', to: 'holdout_eval', input: '0' })
  })

  it('orders dependencies before consumers with effective-key priority', () => {
    const order = topologicalOrder(mainCells).map((cell) => cell.slug)
    expect(order.indexOf('features')).toBeLessThan(order.indexOf('train_model'))
    expect(order.indexOf('train_model')).toBeLessThan(order.indexOf('holdout_eval'))
    expect(order.indexOf('holdout_eval')).toBeLessThan(order.indexOf('roc_curve'))
    // Deterministic: same input, same order.
    expect(topologicalOrder(mainCells).map((cell) => cell.slug)).toEqual(order)
  })

  it('inserts an anchored downstream cell without reflowing existing cards', () => {
    const chain = [
      authoredCell('load_data', 2),
      authoredCell('eda', 4, 'load_data.rows'),
      authoredCell('split', 6, 'eda.frame'),
      authoredCell('train', 8, 'split.train'),
    ]
    const before = topologicalOrder(chain).map((cell) => cell.slug)
    const inserted = {
      ...authoredCell('untitled_1', 10, 'eda.frame'),
      order: '5',
    }

    expect(topologicalOrder([...chain, inserted]).map((cell) => cell.slug)).toEqual([
      'load_data',
      'eda',
      'untitled_1',
      'split',
      'train',
    ])
    expect(
      topologicalOrder([...chain, inserted])
        .filter((cell) => cell.slug !== inserted.slug)
        .map((cell) => cell.slug),
    ).toEqual(before)
  })

  it('compares midpoint keys without losing decimal precision', () => {
    const later = {
      ...authoredCell('later', 2),
      order: '4.0000000000000000000000000000000000002',
    }
    const earlier = {
      ...authoredCell('earlier', 3),
      order: '4.0000000000000000000000000000000000001',
    }

    expect(topologicalOrder([later, earlier]).map((cell) => cell.slug)).toEqual([
      'earlier',
      'later',
    ])
  })

  it('disables an adjacent move that would cross a producer or consumer', () => {
    const cells = [
      authoredCell('load', 2),
      authoredCell('train_model', 4, 'load.rows'),
      authoredCell('evaluate', 6, 'train_model.model'),
      authoredCell('notes', 8),
    ]
    const neighbours = reorderNeighbours(cells)

    expect(neighbours.get('evaluate')).toEqual({ up: null, down: 'notes' })
    expect(neighbours.get('train_model')?.down).toBeNull()
    expect(neighbours.get('notes')?.up).toBe('evaluate')
  })

  it('keeps the column pinned when an unrelated cell lands', () => {
    const chain = [
      authoredCell('load', 2),
      authoredCell('features', 4, 'load.rows'),
      authoredCell('train_model', 6, 'features.split'),
      authoredCell('holdout_eval', 8, 'train_model.model'),
    ]
    const before = topologicalOrder(chain).map((cell) => cell.slug)
    expect(before).toEqual(['load', 'features', 'train_model', 'holdout_eval'])

    // A root nobody reads, ordered last: it belongs at the bottom, where it was
    // written. Landing it above cells minted before it would move every card
    // under it down a slot — the effective-key priority rules out.
    const after = topologicalOrder([...chain, authoredCell('alpha_scan', 12)])
    expect(after.map((cell) => cell.slug)).toEqual([...before, 'alpha_scan'])
  })

  it('parses producers from reference strings', () => {
    expect(producerOf('features.train_split')).toBe('features')
    expect(producerOf('train_split')).toBe('train_split')
  })
})

describe('fixture integrity', () => {
  it('resolves every consumes reference within its branch slice', () => {
    for (const [branch, cells] of Object.entries(cellsByBranch)) {
      const slugs = new Set(cells.map((cell) => cell.slug))
      for (const cell of cells) {
        if (cell.flag) continue // deliberately dangling (did-you-mean specimen)
        for (const reference of cell.consumes) {
          expect(slugs.has(producerOf(reference)), `${branch}: ${cell.slug} → ${reference}`).toBe(
            true,
          )
        }
      }
    }
  })

  it('gives every branch a resolvable parent and every slice a branch record', () => {
    const names = new Set(branches.map((branch) => branch.name))
    for (const branch of branches) {
      if (branch.parent !== null) expect(names.has(branch.parent)).toBe(true)
    }
    for (const name of Object.keys(cellsByBranch)) expect(names.has(name)).toBe(true)
  })

  it('marks stale cells with a worded cause, and only stale cells', () => {
    for (const cells of Object.values(cellsByBranch)) {
      for (const cell of cells) {
        if (cell.status === 'stale') {
          expect(cell.stale?.cause, cell.slug).toBeTruthy()
          expect(cell.stale?.cause).not.toMatch(/^(definition-changed|deps-rewired)$/)
        }
        if (cell.status === 'unmaterialized') expect(cell.stale).toBeUndefined()
      }
    }
  })

  it('leaks no internal identifiers into user-facing strings', () => {
    const userFacing: string[] = []
    for (const cells of Object.values(cellsByBranch)) {
      for (const cell of cells) {
        userFacing.push(cell.slug, cell.doc, cell.stale?.cause ?? '', cell.provenance?.intent ?? '')
      }
    }
    for (const entry of churnFixture.journal) userFacing.push(entry.intent, entry.summary)
    const blob = userFacing.join('\n')
    expect(blob).not.toMatch(/\buid\b/i)
    expect(blob).not.toMatch(/memo key/i)
    expect(blob).not.toMatch(/\b[0-9a-f]{12,}\b/i) // hash-looking tokens
    expect(blob).not.toMatch(/\b[0-7][0-9A-HJKMNP-TV-Z]{25}\b/) // ULIDs
  })
})

describe('formatters', () => {
  it('formats costs across magnitudes', () => {
    expect(formatCost(0.04)).toBe('<0.1s')
    expect(formatCost(9.8)).toBe('9.8s')
    expect(formatCost(312)).toBe('5m 12s')
    expect(formatCost(5400)).toBe('1h 30m')
  })

  it('formats bytes and metrics', () => {
    expect(formatBytes(890)).toBe('890 B')
    expect(formatBytes(14_680_064)).toBe('14.0 MB')
    expect(formatMetric(0.8412)).toBe('0.841')
    expect(formatMetric(0.00032)).toBe('3.2e-4')
    expect(formatMetric(Number.NaN)).toBe('nan')
    expect(formatMetric(Number.POSITIVE_INFINITY)).toBe('inf')
    expect(formatMetric(Number.NEGATIVE_INFINITY)).toBe('-inf')
    expect(formatMetric(84312)).toBe('84312')
  })
})
