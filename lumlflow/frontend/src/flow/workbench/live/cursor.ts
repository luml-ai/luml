export const CURSOR_STORAGE_PREFIX = 'lumlflow.flow.cursor:'

export type CursorStorage = Pick<Storage, 'getItem' | 'setItem'>

export interface StoredCursor {
  flowId: string
  step: number
}

export function cursorKey(flow: string): string {
  return `${CURSOR_STORAGE_PREFIX}${flow}`
}

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
  }
}

export function browserCursorStorage(): CursorStorage | null {
  if (typeof window === 'undefined') return null
  try {
    return window.localStorage
  } catch {
    return null
  }
}
