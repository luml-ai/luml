export type WorkbenchSource = 'live' | 'unconnected'

export function selectSource(token: string | null): WorkbenchSource {
  return token ? 'live' : 'unconnected'
}
