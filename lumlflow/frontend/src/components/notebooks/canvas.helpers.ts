import type { CellSummary } from '@/api/slices/workspace/workspace.interface'
import type { CellEdge } from '@/components/notebooks/notebooks.interface'

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
