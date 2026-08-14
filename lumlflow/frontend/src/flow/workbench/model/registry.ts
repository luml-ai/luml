import type { AssetKind, CellOutput, FlowCell } from './types'

/**
 * Which output opens first matters more than it looks: a training cell that
 * returns {model, run, checkpoint, curves} must open on the experiment, not on
 * whichever key came first.
 *
 * The daemon names the primary output and this is the fallback for when it has
 * not, so the two orders have to be the same one — this is `_KIND_ORDER` in
 * `flow/daemon/queries.py`, kind for kind. `unknown` stands in for `pickle`
 * (the daemon's last listed kind, and what an unrecognised kind reads as here);
 * kinds absent from the list — the attachment kinds, a workspace plugin's own —
 * rank after it.
 */
const PRIMARY_RANKING: AssetKind[] = [
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

export function rankOf(kind: AssetKind): number {
  const index = PRIMARY_RANKING.indexOf(kind)
  return index === -1 ? PRIMARY_RANKING.length : index
}

export function primaryOutput(cell: FlowCell): CellOutput | null {
  if (cell.outputs.length === 0) return null
  if (cell.primaryOutput) {
    const declared = cell.outputs.find((output) => output.name === cell.primaryOutput)
    if (declared) return declared
  }
  return [...cell.outputs].sort((a, b) => rankOf(a.kind) - rankOf(b.kind))[0]
}

export const KIND_LABELS: Record<AssetKind, string> = {
  frame: 'frame',
  plot: 'plot',
  metric: 'metric',
  note: 'note',
  eval: 'eval',
  model: 'model',
  dataset: 'dataset',
  experiment: 'experiment',
  checkpoint: 'checkpoint',
  file: 'file',
  image: 'image',
  text: 'text',
  html: 'html',
  unknown: 'asset',
}

/** Producer slug of a reference string: 'features.train_split' → 'features'. */
export function producerOf(reference: string): string {
  const dot = reference.indexOf('.')
  return dot === -1 ? reference : reference.slice(0, dot)
}

/** Edges of a branch slice, derived from declared wiring. */
export function sliceEdges(cells: FlowCell[]): { from: string; to: string }[] {
  const slugs = new Set(cells.map((cell) => cell.slug))
  const edges: { from: string; to: string }[] = []
  for (const cell of cells) {
    for (const reference of cell.consumes) {
      const from = producerOf(reference)
      if (slugs.has(from) && from !== cell.slug) edges.push({ from, to: cell.slug })
    }
  }
  return edges
}

/**
 * The step a cell was minted at, which breaks ordering ties — a fact that
 * never moves, so neither an edit nor a rename can reorder the column. A card
 * with neither that nor an authorship read yet sorts last rather than first: it
 * would otherwise jump to the top of the column and then move once it loads.
 */
export function authored(cell: FlowCell): number {
  return cell.authoredStep ?? cell.provenance?.step ?? Number.MAX_SAFE_INTEGER
}

/**
 * Stable topological order for the notebook view: dependencies first, and among
 * the cells no dependency separates, the earlier-minted one reads first.
 *
 * The pick is one cell at a time rather than a whole ready layer, and that is
 * the part that keeps the promise. A layer would emit every parentless cell
 * before anything downstream, so a root written last would land above cells
 * minted long before it — a new card appearing mid-column, which is the reorder
 * the mint-order tiebreak exists to prevent.
 */
export function topologicalOrder(cells: FlowCell[]): FlowCell[] {
  const bySlug = new Map(cells.map((cell) => [cell.slug, cell]))
  const edges = sliceEdges(cells)
  const incoming = new Map<string, Set<string>>()
  for (const cell of cells) incoming.set(cell.slug, new Set())
  for (const edge of edges) incoming.get(edge.to)?.add(edge.from)

  const byMintOrder = (a: FlowCell, b: FlowCell): number => authored(a) - authored(b)
  const held = (slugs: Iterable<string>): FlowCell[] =>
    [...slugs].map((slug) => bySlug.get(slug) as FlowCell).sort(byMintOrder)

  const ordered: FlowCell[] = []
  while (incoming.size > 0) {
    const [next] = held(
      [...incoming.entries()].filter(([, deps]) => deps.size === 0).map(([slug]) => slug),
    )
    if (next === undefined) {
      // Cycle or dangling reference: append the rest in authoring order.
      ordered.push(...held(incoming.keys()))
      break
    }
    ordered.push(next)
    incoming.delete(next.slug)
    for (const deps of incoming.values()) deps.delete(next.slug)
  }
  return ordered
}
