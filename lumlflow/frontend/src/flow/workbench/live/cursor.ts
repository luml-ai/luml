/**
 * Where this browser got to on a flow, kept across reopens.
 *
 * The catch-up marker answers one question — *what landed while I was away* —
 * and a tab that forgets its cursor the moment it closes can never ask it: it
 * reopens, catches up from zero, and is by construction never behind. So the
 * step is written down, per flow and per origin, beside the token that is
 * already kept there.
 *
 * Storage is best-effort on purpose. A browser that refuses it (private mode, a
 * quota, a disabled origin) costs the reader a marker, and never the workbench:
 * a cursor that cannot be read is the same as one that was never written, which
 * is exactly a first load.
 */

export const CURSOR_STORAGE_PREFIX = 'lumlflow.flow.cursor:'

export type CursorStorage = Pick<Storage, 'getItem' | 'setItem'>

export function cursorKey(flow: string): string {
  return `${CURSOR_STORAGE_PREFIX}${flow}`
}

/** The step this browser last watched on `flow`, or null if it never has. */
export function readCursor(flow: string, storage: CursorStorage | null): number | null {
  if (!flow || storage === null) return null
  let held: string | null
  try {
    held = storage.getItem(cursorKey(flow))
  } catch {
    return null
  }
  if (held === null) return null
  const step = Number(held)
  return Number.isFinite(step) && step >= 0 ? step : null
}

export function writeCursor(flow: string, step: number, storage: CursorStorage | null): void {
  if (!flow || storage === null || !Number.isFinite(step) || step < 0) return
  try {
    storage.setItem(cursorKey(flow), String(step))
  } catch {
    // Out of quota, or an origin that holds nothing. The marker is worth no
    // more than the gesture it decorates.
  }
}

/** The browser's own, or null where there is none to speak of. */
export function browserCursorStorage(): CursorStorage | null {
  if (typeof window === 'undefined') return null
  try {
    return window.localStorage
  } catch {
    return null
  }
}
