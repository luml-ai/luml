/**
 * Where a flow's workbench lives in the URL.
 *
 * A flow is addressed by the path the daemon knows it by: root-relative under
 * the launch directory (`churn.flow`, `data/sweep.flow`), absolute above it
 * (`/home/dana/projects/sales.flow`). Both are one route parameter, so a path
 * that carries separators is percent-encoded into a single segment rather than
 * spread over several — `:flowId` matches one segment, and a route greedy
 * enough to match more would also swallow `/notebook` and `/compare`.
 *
 * Encoded, never climbed: a literal `../` in a URL is resolved away by the
 * browser before the router ever sees it, and so is its encoded spelling, so
 * an outside flow names where it is rather than how to get there from here.
 */

export type FlowView = '' | '/notebook' | '/compare'

export function flowPath(flowId: string, view: FlowView = ''): string {
  return `/flow/${encodeURIComponent(flowId)}${view}`
}
