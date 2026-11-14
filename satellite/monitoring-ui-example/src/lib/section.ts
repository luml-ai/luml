import { SectionState } from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'

export type SectionView = 'loading' | 'error' | 'empty' | 'ready'

/**
 * Collapse a fetch status and the response's own SectionState into one render decision.
 *
 * A refetch with a previous response in hand keeps rendering that response instead of
 * flashing a skeleton: the skeleton means "nothing to show yet", which is only true on
 * the first load. `state` is undefined exactly while no response has ever arrived.
 */
export function sectionView(
  status: LoadStatus,
  state: SectionState | null | undefined,
): SectionView {
  if (status === 'error' || state === SectionState.UNAVAILABLE) return 'error'
  if (status === 'idle' || (status === 'loading' && state == null)) return 'loading'
  if (state === SectionState.EMPTY) return 'empty'
  return 'ready'
}
