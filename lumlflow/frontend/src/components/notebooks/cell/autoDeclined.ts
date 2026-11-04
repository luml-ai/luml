import type { CellAutoDeclined } from '@/api/slices/workspace/workspace.interface'

function seconds(value: number): string {
  if (value < 1) return 'under a second'
  return `about ${Math.round(value)} s`
}

/**
 * Why reactivity left a stale cell for the user to run, in one line for its
 * card. Reactivity settings promise the card says so; without this it only
 * read "Out of date".
 */
export function autoDeclinedText(
  declined: CellAutoDeclined | null | undefined,
  thresholdSeconds: number,
): string {
  if (!declined) return ''
  switch (declined.reason) {
    case 'too-expensive':
      return `Not refreshed automatically: takes ${seconds(declined.estimate_seconds)}, over the ${thresholdSeconds} s auto limit. Run it when ready.`
    case 'never-timed': {
      const cells = declined.untimed.map((slug) => `\`${slug}\``).join(', ')
      return cells
        ? `Not refreshed automatically: ${cells} never ran here, so the cost is unknown. Run it once.`
        : 'Not refreshed automatically: its cost is unknown. Run it once.'
    }
    default:
      return declined.detail
        ? `Not refreshed automatically: ${declined.detail}`
        : 'Not refreshed automatically. Run it when ready.'
  }
}
