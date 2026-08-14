import type { HandoffGesture } from '@/flow/api/types'
import type { FlowCell } from '../../model/types'

export type { HandoffGesture }

/** What each gesture asks the agent for, in the words the popover shows. */
export const GESTURE_LINES: Record<HandoffGesture, string> = {
  fix: 'fix this cell. the payload carries the traceback.',
  explain: 'explain this cell on this lane',
  diff: 'explain how the compared lanes differ',
  summarize: 'summarize this lane as a note cell',
}

/**
 * The context payload handed to the agent (ui-draft §4 / §15) as a compact
 * fenced block an agent CLI can consume. The address is slug + branch + step
 * only — internal ids, hashes, and memo keys never leave the store.
 *
 * The daemon builds this for a live session — it holds facts no card has, like
 * the traceback of a run nobody opened the logs of. This is the fixture-mode
 * builder behind it, and the shape the daemon's own answer follows.
 */
export function buildHandoffPayload(
  cell: FlowCell,
  branch: string,
  gesture: HandoffGesture,
): string {
  const lines = [
    '```lumlflow-context',
    `gesture: ${gesture}`,
    `branch: ${branch}`,
    `cell: ${cell.slug}`,
  ]
  if (cell.provenance) lines.push(`step: ${cell.provenance.step}`)
  if (cell.doc) lines.push(`doc: ${cell.doc}`)
  if (cell.error) {
    lines.push(`error: ${cell.error.summary}`)
    lines.push('traceback: |')
    for (const row of cell.error.traceback.split('\n')) lines.push(`  ${row}`)
  }
  lines.push('```')
  return lines.join('\n')
}
