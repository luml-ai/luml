import {
  compareOrder,
  effectiveOrder,
  producerOf,
  sliceEdges,
  topologicalOrder,
} from '../../model/registry'
import type { FlowCell } from '../../model/types'

export const NODE_WIDTH = 460
export const NODE_HEIGHT = 560
const COLUMN_GAP = 140
const ROW_GAP = 56
const SLOT = NODE_HEIGHT + ROW_GAP

export interface CanvasPosition {
  x: number
  y: number
}

export interface CanvasLayout {
  positions: Record<string, CanvasPosition>
  orders: Record<string, string>
  wiring: Record<string, string>
}

export function cellIdentity(cell: FlowCell): string {
  return cell.uid || cell.slug
}

export function createCanvasLayout(cells: FlowCell[]): CanvasLayout {
  const description = describe(cells)
  return { ...description, positions: positionsFor(cells) }
}

export function updateCanvasLayout(previous: CanvasLayout, cells: FlowCell[]): CanvasLayout {
  const description = describe(cells)
  const retained = Object.keys(description.wiring).filter((uid) => uid in previous.wiring)
  if (retained.some((uid) => description.wiring[uid] !== previous.wiring[uid])) {
    return createCanvasLayout(cells)
  }

  const ideal = positionsFor(cells)
  const positions: Record<string, CanvasPosition> = {}
  const toPlace: string[] = []
  for (const cell of cells) {
    const uid = cellIdentity(cell)
    if (previous.positions[uid] && previous.orders[uid] === description.orders[uid]) {
      positions[uid] = previous.positions[uid]
    } else {
      toPlace.push(uid)
    }
  }

  toPlace.sort((left, right) => {
    const a = ideal[left] ?? { x: 0, y: 0 }
    const b = ideal[right] ?? { x: 0, y: 0 }
    return (
      a.x - b.x || a.y - b.y || compareOrder(description.orders[left], description.orders[right])
    )
  })
  for (const uid of toPlace) {
    const movedUp =
      previous.orders[uid] !== undefined &&
      compareOrder(description.orders[uid], previous.orders[uid]) < 0
    positions[uid] = firstOpenSlot(ideal[uid] ?? { x: 0, y: 0 }, positions, movedUp ? -1 : 1)
  }

  return { ...description, positions }
}

function describe(cells: FlowCell[]): Omit<CanvasLayout, 'positions'> {
  const bySlug = new Map(cells.map((cell) => [cell.slug, cell]))
  const orders: Record<string, string> = {}
  const wiring: Record<string, string> = {}
  for (const cell of cells) {
    const uid = cellIdentity(cell)
    orders[uid] = effectiveOrder(cell)
    const consumed = cell.consumesByInput
      ? Object.entries(cell.consumesByInput)
      : cell.consumes.map((reference, index) => [String(index), reference] as const)
    wiring[uid] = JSON.stringify(
      consumed
        .map(([input, reference]) => [input, stableReference(reference, bySlug)] as const)
        .sort(([left], [right]) => left.localeCompare(right)),
    )
  }
  return { orders, wiring }
}

function stableReference(reference: string, bySlug: Map<string, FlowCell>): string {
  const producer = producerOf(reference)
  const output = reference.includes('.') ? reference.slice(reference.indexOf('.') + 1) : ''
  const parent = bySlug.get(producer)
  return `${parent ? `uid:${cellIdentity(parent)}` : `slug:${producer}`}.${output}`
}

function positionsFor(cells: FlowCell[]): Record<string, CanvasPosition> {
  const parents = new Map(cells.map((cell) => [cell.slug, new Set<string>()]))
  for (const edge of sliceEdges(cells)) parents.get(edge.to)?.add(edge.from)

  const ordered = topologicalOrder(cells)
  const columns = new Map<string, number>()
  const preceding = new Map<string, string>()
  let previous: FlowCell | undefined
  for (const cell of ordered) {
    const cellParents = [...(parents.get(cell.slug) ?? [])]
    if (cellParents.length > 0) {
      const parentColumns = cellParents
        .map((slug) => columns.get(slug))
        .filter((column): column is number => column !== undefined)
      columns.set(cell.slug, parentColumns.length > 0 ? Math.max(...parentColumns) + 1 : 0)
    } else if (previous) {
      columns.set(cell.slug, columns.get(previous.slug) ?? 0)
      preceding.set(cell.slug, previous.slug)
    } else {
      columns.set(cell.slug, 0)
    }
    previous = cell
  }

  const layers = new Map<number, FlowCell[]>()
  for (const cell of cells) {
    const column = columns.get(cell.slug) ?? 0
    const bucket = layers.get(column) ?? []
    bucket.push(cell)
    layers.set(column, bucket)
  }

  const rows = new Map<string, number>()
  const barycenters = new Map<string, number>()
  const positions: Record<string, CanvasPosition> = {}
  for (const column of [...layers.keys()].sort((left, right) => left - right)) {
    const bucket = layers.get(column) ?? []
    bucket.sort((left, right) => compareOrder(effectiveOrder(left), effectiveOrder(right)))
    for (const cell of bucket) {
      const cellParents = [...(parents.get(cell.slug) ?? [])]
      const parentRows = cellParents
        .map((slug) => rows.get(slug))
        .filter((row): row is number => row !== undefined)
      if (parentRows.length > 0) {
        barycenters.set(
          cell.slug,
          parentRows.reduce((total, row) => total + row, 0) / parentRows.length,
        )
      } else {
        const anchor = preceding.get(cell.slug)
        barycenters.set(cell.slug, anchor ? (barycenters.get(anchor) ?? 0) : 0)
      }
    }
    bucket.sort((left, right) => {
      const barycenter = (barycenters.get(left.slug) ?? 0) - (barycenters.get(right.slug) ?? 0)
      return barycenter || compareOrder(effectiveOrder(left), effectiveOrder(right))
    })
    bucket.forEach((cell, row) => {
      rows.set(cell.slug, row)
      positions[cellIdentity(cell)] = {
        x: column * (NODE_WIDTH + COLUMN_GAP),
        y: row * SLOT,
      }
    })
  }
  return positions
}

function firstOpenSlot(
  candidate: CanvasPosition,
  positions: Record<string, CanvasPosition>,
  direction: -1 | 1,
): CanvasPosition {
  let y = candidate.y
  const occupied = Object.values(positions)
  while (
    occupied.some((position) => position.x === candidate.x && Math.abs(position.y - y) < SLOT)
  ) {
    y += direction * SLOT
  }
  return { x: candidate.x, y }
}
