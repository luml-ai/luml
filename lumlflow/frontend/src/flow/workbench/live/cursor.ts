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

export interface StoredCursor {
  flowId: string
  step: number
}

export function cursorKey(flow: string): string {
  return `${CURSOR_STORAGE_PREFIX}${flow}`
}

/** The flow identity and step this browser last watched, or null on a first load. */
export function readCursor(flow: string, storage: CursorStorage | null): StoredCursor | null {
  if (!flow || storage === null) return null
  let held: string | null
  try {
    held = storage.getItem(cursorKey(flow))
  } catch {
    return null
  }
  if (held === null) return null
  let decoded: unknown
  try {
    decoded = JSON.parse(held)
  } catch {
    return null
  }
  if (typeof decoded !== 'object' || decoded === null) return null
  const flowId = Reflect.get(decoded, 'flowId')
  const step = Reflect.get(decoded, 'step')
  return typeof flowId === 'string' && flowId && typeof step === 'number' && step >= 0
    ? { flowId, step }
    : null
}

export function writeCursor(
  flow: string,
  flowId: string,
  step: number,
  storage: CursorStorage | null,
): void {
  if (!flow || !flowId || storage === null || !Number.isFinite(step) || step < 0) return
  try {
    storage.setItem(cursorKey(flow), JSON.stringify({ flowId, step }))
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
