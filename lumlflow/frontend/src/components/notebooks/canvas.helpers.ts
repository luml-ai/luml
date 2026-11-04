import type { CellSummary } from '@/api/slices/workspace/workspace.interface'
import type {
  CanvasLayoutSize,
  CanvasPosition,
  CellEdge,
} from '@/components/notebooks/notebooks.interface'

function producerOf(reference: string): string {
  const dot = reference.lastIndexOf('.')
  return dot === -1 ? reference : reference.slice(0, dot)
}

export function buildEdges(cells: CellSummary[]): CellEdge[] {
  const slugs = new Set(cells.map((cell) => cell.slug))
  const edges: CellEdge[] = []
  for (const cell of cells) {
    for (const [input, reference] of Object.entries(cell.consumes)) {
      const from = producerOf(reference)
      if (slugs.has(from) && from !== cell.slug) edges.push({ from, to: cell.slug, input })
    }
  }
  return edges
}

export function edgesLeadingTo(edges: CellEdge[], slug: string | null): Set<string> {
  const lit = new Set<string>()
  if (!slug) return lit
  const incoming = new Map<string, CellEdge[]>()
  for (const edge of edges) {
    const held = incoming.get(edge.to) ?? []
    held.push(edge)
    incoming.set(edge.to, held)
  }
  const visited = new Set<string>()
  const pending = [slug]
  while (pending.length) {
    const current = pending.pop() as string
    if (visited.has(current)) continue
    visited.add(current)
    for (const edge of incoming.get(current) ?? []) {
      lit.add(edgeId(edge))
      pending.push(edge.from)
    }
  }
  return lit
}

export function edgeId(edge: CellEdge): string {
  return `e-${edge.from}-${edge.to}-${edge.input}`
}

function buildLevels(cells: CellSummary[], edges: CellEdge[]): Map<string, number> {
  const parents = new Map<string, string[]>(cells.map((cell) => [cell.slug, []]))
  for (const edge of edges) parents.get(edge.to)?.push(edge.from)

  const levels = new Map<string, number>()
  function levelOf(slug: string, guard: Set<string>): number {
    if (levels.has(slug)) return levels.get(slug) as number
    if (guard.has(slug)) return 0
    guard.add(slug)
    const cellParents = parents.get(slug) ?? []
    const level =
      cellParents.length === 0
        ? 0
        : 1 + Math.max(...cellParents.map((parent) => levelOf(parent, guard)))
    levels.set(slug, level)
    return level
  }
  for (const cell of cells) levelOf(cell.slug, new Set())
  return levels
}

export function autoLayout(
  cells: CellSummary[],
  edges: CellEdge[],
  size: CanvasLayoutSize,
): Map<string, CanvasPosition> {
  const levels = buildLevels(cells, edges)
  const layers = new Map<number, string[]>()
  for (const cell of cells) {
    const level = levels.get(cell.slug) ?? 0
    const bucket = layers.get(level) ?? []
    bucket.push(cell.slug)
    layers.set(level, bucket)
  }

  const positions = new Map<string, CanvasPosition>()
  for (const [level, slugs] of layers) {
    const width = slugs.length * size.width
    slugs.forEach((slug, index) => {
      positions.set(slug, {
        x: index * size.width - width / 2 + size.width / 2,
        y: level * size.height,
      })
    })
  }
  return positions
}

function overlaps(left: CanvasPosition, right: CanvasPosition, size: CanvasLayoutSize): boolean {
  return Math.abs(left.x - right.x) < size.width && Math.abs(left.y - right.y) < size.height
}

export function layoutCells(
  cells: CellSummary[],
  edges: CellEdge[],
  stored: Record<string, CanvasPosition>,
  size: CanvasLayoutSize,
): Map<string, CanvasPosition> {
  const auto = autoLayout(cells, edges, size)
  const positions = new Map<string, CanvasPosition>()
  for (const cell of cells) {
    const kept = stored[cell.slug]
    if (kept) positions.set(cell.slug, { x: kept.x, y: kept.y })
  }
  if (positions.size === 0) return auto

  for (const cell of cells) {
    if (positions.has(cell.slug)) continue
    const start = auto.get(cell.slug) ?? { x: 0, y: 0 }
    const placed = [...positions.values()]
    let candidate = start
    for (let step = 1; placed.some((other) => overlaps(candidate, other, size)); step++) {
      const offset = Math.ceil(step / 2) * (step % 2 === 1 ? 1 : -1)
      candidate = { x: start.x + offset * size.width, y: start.y }
    }
    positions.set(cell.slug, candidate)
  }
  return positions
}
