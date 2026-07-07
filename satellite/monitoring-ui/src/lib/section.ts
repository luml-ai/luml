import { SectionState } from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'

export type SectionView = 'loading' | 'error' | 'empty' | 'ready'

/** Collapse a fetch status and the response's own SectionState into one render decision. */
export function sectionView(
  status: LoadStatus,
  state: SectionState | null | undefined,
): SectionView {
  if (status === 'idle' || status === 'loading') return 'loading'
  if (status === 'error' || state === SectionState.UNAVAILABLE) return 'error'
  if (state === SectionState.EMPTY) return 'empty'
  return 'ready'
}
