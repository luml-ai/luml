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

export interface SliceEdge {
  from: string
  to: string
  input: string
}

/** Edges of a branch slice, including the consumer input that distinguishes them. */
export function sliceEdges(cells: FlowCell[]): SliceEdge[] {
  const slugs = new Set(cells.map((cell) => cell.slug))
  const edges: SliceEdge[] = []
  for (const cell of cells) {
    const consumed = cell.consumesByInput
      ? Object.entries(cell.consumesByInput)
      : cell.consumes.map((reference, index) => [String(index), reference] as const)
    for (const [input, reference] of consumed) {
      const from = producerOf(reference)
      if (slugs.has(from) && from !== cell.slug) edges.push({ from, to: cell.slug, input })
    }
  }
  return edges
}

/** The immutable mint step used when a flow has no explicit order key. */
export function authored(cell: FlowCell): number {
  return cell.authoredStep ?? cell.provenance?.step ?? Number.MAX_SAFE_INTEGER
}

/** Decimal text is the wire format because repeated midpoints can exceed JS precision. */
export function effectiveOrder(cell: FlowCell): string {
  return cell.order ?? String(authored(cell))
}

interface DecimalParts {
  negative: boolean
  whole: string
  fraction: string
}

function decimalParts(value: string): DecimalParts {
  const negative = value.startsWith('-')
  const unsigned = value.replace(/^[+-]/, '')
  const [wholePart = '0', fractionPart = ''] = unsigned.split('.', 2)
  const whole = wholePart.replace(/^0+/, '') || '0'
  const fraction = fractionPart.replace(/0+$/, '')
  return {
    negative: negative && (whole !== '0' || fraction !== ''),
    whole,
    fraction,
  }
}

function compareMagnitude(left: DecimalParts, right: DecimalParts): number {
  if (left.whole.length !== right.whole.length) return left.whole.length - right.whole.length
  const whole = left.whole.localeCompare(right.whole)
  if (whole !== 0) return whole
  const width = Math.max(left.fraction.length, right.fraction.length)
  return left.fraction.padEnd(width, '0').localeCompare(right.fraction.padEnd(width, '0'))
}

export function compareOrder(left: string, right: string): number {
  const a = decimalParts(left)
  const b = decimalParts(right)
  if (a.negative !== b.negative) return a.negative ? -1 : 1
  const magnitude = compareMagnitude(a, b)
  return a.negative ? -magnitude : magnitude
}

/**
 * Stable topological order for the notebook view: dependencies first, and among
 * the cells no dependency separates, the lower effective key reads first.
 *
 * The pick is one cell at a time rather than a whole ready layer, and that is
 * the part that keeps the promise. A layer would emit every parentless cell
 * before anything downstream, so a root written last would land above cells
 * minted long before it — a new card appearing mid-column, which is the reorder
 * the effective-key priority exists to prevent.
 */
export function topologicalOrder(cells: FlowCell[]): FlowCell[] {
  const bySlug = new Map(cells.map((cell) => [cell.slug, cell]))
  const edges = sliceEdges(cells)
  const incoming = new Map<string, Set<string>>()
  for (const cell of cells) incoming.set(cell.slug, new Set())
  for (const edge of edges) incoming.get(edge.to)?.add(edge.from)

  const byEffectiveOrder = (a: FlowCell, b: FlowCell): number =>
    compareOrder(effectiveOrder(a), effectiveOrder(b))
  const held = (slugs: Iterable<string>): FlowCell[] =>
    [...slugs].map((slug) => bySlug.get(slug) as FlowCell).sort(byEffectiveOrder)

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

export interface ReorderNeighbours {
  up: string | null
  down: string | null
}

/** Adjacent notebook moves that preserve this lane's producer ordering. */
export function reorderNeighbours(cells: FlowCell[]): Map<string, ReorderNeighbours> {
  const ordered = topologicalOrder(cells)
  return new Map(
    ordered.map((cell, index) => {
      const previous = ordered[index - 1]
      const next = ordered[index + 1]
      return [
        cell.slug,
        {
          up: previous && canPlaceBeside(cells, cell, previous, 'before') ? previous.slug : null,
          down: next && canPlaceBeside(cells, cell, next, 'after') ? next.slug : null,
        },
      ]
    }),
  )
}

function canPlaceBeside(
  cells: FlowCell[],
  moved: FlowCell,
  neighbour: FlowCell,
  side: 'before' | 'after',
): boolean {
  const bySlug = new Map(cells.map((cell) => [cell.slug, cell]))
  const producers = moved.consumes
    .map(producerOf)
    .map((slug) => bySlug.get(slug))
    .filter((cell): cell is FlowCell => cell !== undefined && cell.slug !== moved.slug)
  const consumers = cells.filter(
    (cell) =>
      cell.slug !== moved.slug && cell.consumes.some((ref) => producerOf(ref) === moved.slug),
  )
  const boundary = effectiveOrder(neighbour)
  if (side === 'before') {
    return (
      producers.every((cell) => compareOrder(effectiveOrder(cell), boundary) < 0) &&
      consumers.every((cell) => compareOrder(effectiveOrder(cell), boundary) >= 0)
    )
  }
  return (
    producers.every((cell) => compareOrder(effectiveOrder(cell), boundary) <= 0) &&
    consumers.every((cell) => compareOrder(effectiveOrder(cell), boundary) > 0)
  )
}
