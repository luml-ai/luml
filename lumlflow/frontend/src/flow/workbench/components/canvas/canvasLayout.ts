import { authored, sliceEdges } from '../../model/registry'
import type { FlowCell, Slug } from '../../model/types'

/**
 * Layered left-to-right DAG layout over the declared wiring: a cell's layer is
 * its longest path from a root, so a card always sits right of everything it
 * reads. Within a layer, cells pack vertically ordered by the barycenter of
 * their parents (authoring step as the tiebreak), which keeps edges short
 * without a full crossing-minimization pass.
 */

export const NODE_WIDTH = 460
const NODE_SLOT_HEIGHT = 560
const COLUMN_GAP = 140
const ROW_GAP = 56

export interface CanvasPosition {
  x: number
  y: number
}

export function layoutSlice(cells: FlowCell[]): Record<Slug, CanvasPosition> {
  const parentsOf = new Map<Slug, Slug[]>()
  for (const cell of cells) parentsOf.set(cell.slug, [])
  for (const edge of sliceEdges(cells)) parentsOf.get(edge.to)?.push(edge.from)

  const depth = new Map<Slug, number>()
  const visiting = new Set<Slug>()
  const resolve = (slug: Slug): number => {
    const known = depth.get(slug)
    if (known !== undefined) return known
    if (visiting.has(slug)) return 0
    visiting.add(slug)
    const parents = parentsOf.get(slug) ?? []
    const value = parents.length ? Math.max(...parents.map(resolve)) + 1 : 0
    visiting.delete(slug)
    depth.set(slug, value)
    return value
  }
  for (const cell of cells) resolve(cell.slug)

  const layers = new Map<number, FlowCell[]>()
  for (const cell of cells) {
    const layer = depth.get(cell.slug) ?? 0
    const bucket = layers.get(layer) ?? []
    bucket.push(cell)
    layers.set(layer, bucket)
  }

  const layerIndices = [...layers.keys()].sort((a, b) => a - b)
  const rowIndex = new Map<Slug, number>()
  for (const layer of layerIndices) {
    const bucket = layers.get(layer) ?? []
    const barycenter = (cell: FlowCell): number => {
      const rows = (parentsOf.get(cell.slug) ?? [])
        .map((parent) => rowIndex.get(parent))
        .filter((row): row is number => row !== undefined)
      if (rows.length === 0) return Number.MAX_SAFE_INTEGER
      return rows.reduce((sum, row) => sum + row, 0) / rows.length
    }
    bucket.sort((a, b) => barycenter(a) - barycenter(b) || authored(a) - authored(b))
    bucket.forEach((cell, index) => rowIndex.set(cell.slug, index))
  }

  const slot = NODE_SLOT_HEIGHT + ROW_GAP
  const tallest = Math.max(1, ...layerIndices.map((layer) => layers.get(layer)?.length ?? 0))

  const positions: Record<Slug, CanvasPosition> = {}
  for (const layer of layerIndices) {
    const bucket = layers.get(layer) ?? []
    const offset = ((tallest - bucket.length) * slot) / 2
    bucket.forEach((cell, index) => {
      positions[cell.slug] = {
        x: layer * (NODE_WIDTH + COLUMN_GAP),
        y: offset + index * slot,
      }
    })
  }
  return positions
}
