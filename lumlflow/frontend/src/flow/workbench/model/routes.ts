export type FlowView = '' | '/notebook' | '/compare'

export function flowPath(flowId: string, view: FlowView = ''): string {
  return `/flow/${encodeURIComponent(flowId)}${view}`
}
