import { describe, expect, it } from 'vitest'

import type { CellSummary } from '@/api/slices/workspace/workspace.interface'
import { autoLayout, buildEdges, layoutCells } from '@/components/notebooks/canvas.helpers'

const SIZE = { width: 450, height: 680 }

const cell = (slug: string, consumes: Record<string, string> = {}) =>
  ({ slug, consumes }) as unknown as CellSummary

const CELLS = [
  cell('load'),
  cell('train', { frame: 'load.frame' }),
  cell('evaluate', { frame: 'load.frame' }),
]

function overlapping(positions: Map<string, { x: number; y: number }>): boolean {
  const all = [...positions.values()]
  return all.some((left, at) =>
    all
      .slice(at + 1)
      .some(
        (right) =>
          Math.abs(left.x - right.x) < SIZE.width && Math.abs(left.y - right.y) < SIZE.height,
      ),
  )
}

describe('the canvas layout', () => {
  it('lays the cards out by level when nothing has been arranged', () => {
    const positions = layoutCells(CELLS, buildEdges(CELLS), {}, SIZE)
    expect(positions).toEqual(autoLayout(CELLS, buildEdges(CELLS), SIZE))
    expect(positions.get('load')).toEqual({ x: 0, y: 0 })
    expect(positions.get('train')).toEqual({ x: -225, y: 680 })
    expect(positions.get('evaluate')).toEqual({ x: 225, y: 680 })
  })

  it('keeps every card where the user put it', () => {
    const stored = {
      load: { x: -450, y: -214 },
      train: { x: 10, y: 20 },
      evaluate: { x: 900, y: 900 },
    }
    const positions = layoutCells(CELLS, buildEdges(CELLS), stored, SIZE)
    expect(Object.fromEntries(positions)).toEqual(stored)
  })

  it('keeps a placed card where it is when the graph around it changes', () => {
    const stored = { load: { x: 1000, y: 1000 } }
    const grown = [...CELLS, cell('report', { a: 'train.model', b: 'evaluate.scores' })]
    expect(layoutCells(grown, buildEdges(grown), stored, SIZE).get('load')).toEqual(stored.load)
  })

  it('places a new card so it covers none of the arranged ones', () => {
    const stored = {
      load: { x: 0, y: 0 },
      train: { x: 225, y: 680 },
      evaluate: { x: 675, y: 680 },
    }
    const grown = [...CELLS, cell('score', { frame: 'load.frame' })]
    const positions = layoutCells(grown, buildEdges(grown), stored, SIZE)
    expect(positions.get('train')).toEqual(stored.train)
    expect(positions.get('evaluate')).toEqual(stored.evaluate)
    expect(overlapping(positions)).toBe(false)
  })

  it('ignores positions stored for cells that are not on the lane', () => {
    const stored = { gone: { x: 0, y: 0 } }
    const positions = layoutCells(CELLS, buildEdges(CELLS), stored, SIZE)
    expect(positions.has('gone')).toBe(false)
    expect(positions).toEqual(autoLayout(CELLS, buildEdges(CELLS), SIZE))
  })
})
