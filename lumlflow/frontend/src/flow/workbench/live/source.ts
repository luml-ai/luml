/**
 * Which data a workbench stands on, decided once.
 *
 * Three answers, because two would make one of them a lie. `fixture` is
 * `useWorkbenchState.ts` — the design gallery's data and the tests' — chosen for
 * the `?state=` fixtures that gallery exists to show and when a caller asks for
 * it outright. `live` is a real session. And `unconnected` is the tab that holds
 * no token: it cannot have a live session, and standing it on the fixture would
 * put another flow's cells on screen under this one's name.
 */

import type { RouteLocationNormalizedLoaded } from 'vue-router'

export type WorkbenchSource = 'fixture' | 'live' | 'unconnected'

export function selectSource(
  route: Pick<RouteLocationNormalizedLoaded, 'query'>,
  token: string | null,
): WorkbenchSource {
  if (route.query.source === 'fixture') return 'fixture'
  if (typeof route.query.state === 'string' && route.query.state) return 'fixture'
  return token ? 'live' : 'unconnected'
}
