import type { CellEdge } from '@/components/notebooks/notebooks.interface'

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
