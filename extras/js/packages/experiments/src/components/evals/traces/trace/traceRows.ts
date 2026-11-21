import type { TraceSpan } from '@/interfaces/interfaces'

export interface TraceRow {
  span: TraceSpan
  depth: number
  opened: boolean
}

/** Depth-first rows of the tree in its own order; children of collapsed spans are left out. */
export function flattenTraceTree(tree: TraceSpan[], collapsed: ReadonlySet<string>): TraceRow[] {
  const rows: TraceRow[] = []
  const stack: { span: TraceSpan; depth: number }[] = []
  for (let index = tree.length - 1; index >= 0; index--) {
    stack.push({ span: tree[index]!, depth: 0 })
  }
  while (stack.length) {
    const { span, depth } = stack.pop()!
    const opened = !collapsed.has(span.span_id)
    rows.push({ span, depth, opened })
    if (!opened) continue
    for (let index = span.children.length - 1; index >= 0; index--) {
      stack.push({ span: span.children[index]!, depth: depth + 1 })
    }
  }
  return rows
}

export function spansWithChildren(tree: TraceSpan[]): string[] {
  const ids: string[] = []
  const stack = [...tree]
  while (stack.length) {
    const span = stack.pop()!
    if (!span.children.length) continue
    ids.push(span.span_id)
    for (const child of span.children) stack.push(child)
  }
  return ids
}
