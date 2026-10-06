
import { describe, expect, it } from 'vitest'

import { edgeId, edgesLeadingTo } from '@/components/notebooks/canvas.helpers'
import type { CellEdge } from '@/components/notebooks/notebooks.interface'

const EDGES: CellEdge[] = [
  { from: 'load', to: 'split', input: 'frame' },
  { from: 'split', to: 'train', input: 'train_set' },
  { from: 'split', to: 'evaluate', input: 'test_set' },
  { from: 'train', to: 'report', input: 'model' },
  { from: 'evaluate', to: 'report', input: 'scores' },
]

const ids = (edges: CellEdge[]) => edges.map(edgeId)

describe('the edges leading to a selected cell', () => {
  it('is nothing when nothing is selected, or the cell has no inputs', () => {
    expect(edgesLeadingTo(EDGES, null).size).toBe(0)
    expect(edgesLeadingTo(EDGES, 'load').size).toBe(0)
  })

  it('is the direct inputs and everything above them', () => {
    expect([...edgesLeadingTo(EDGES, 'train')].sort()).toEqual(ids([EDGES[0], EDGES[1]]).sort())
    expect([...edgesLeadingTo(EDGES, 'report')].sort()).toEqual(ids(EDGES).sort())
  })

  it('leaves what is beside or below the cell dark', () => {
    const lit = edgesLeadingTo(EDGES, 'evaluate')
    expect(lit.has(edgeId(EDGES[1]))).toBe(false)
    expect(lit.has(edgeId(EDGES[3]))).toBe(false)
    expect(lit.size).toBe(2)
  })

  it('survives a cycle the graph should not have', () => {
    const looped: CellEdge[] = [...EDGES, { from: 'report', to: 'load', input: 'again' }]
    expect(edgesLeadingTo(looped, 'train').size).toBe(looped.length)
  })
})
