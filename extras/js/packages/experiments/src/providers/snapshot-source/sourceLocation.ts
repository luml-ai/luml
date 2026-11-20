/**
 * Where snapshot bytes are read from. A presigned URL needs nothing else; a storage API such as
 * a workspace Files API also asks for request headers (`Authorization`) or a credentials mode.
 * Only the headers listed here are sent besides `Range`. `Authorization` is the only header
 * allowed; `toSourceLocation` rejects any other.
 */
export interface SnapshotSourceLocation {
  url: string
  headers?: Readonly<Record<string, string>>
  credentials?: RequestCredentials
}

/** A bare URL, or a location with headers. */
export type SnapshotSourceRef = string | SnapshotSourceLocation

/** A location carries a request header other than `Authorization`. */
export class SnapshotSourceHeaderError extends Error {
  constructor(readonly header: string) {
    super(`Snapshot source header '${header}' is not allowed; only Authorization is`)
    this.name = 'SnapshotSourceHeaderError'
  }
}

export function assertSourceHeaders(headers: Readonly<Record<string, string>> | undefined): void {
  // Browsers strip only Authorization on a cross-origin redirect; any other header would reach
  // the redirect target, which may be a third party.
  for (const name of Object.keys(headers ?? {})) {
    if (name.toLowerCase() !== 'authorization') throw new SnapshotSourceHeaderError(name)
  }
}

export function toSourceLocation(ref: SnapshotSourceRef): SnapshotSourceLocation {
  if (typeof ref === 'string') return { url: ref }
  assertSourceHeaders(ref.headers)
  return ref
}

function headerEntries(location: SnapshotSourceLocation): string[] {
  return Object.entries(location.headers ?? {})
    .map(([name, value]) => `${name.toLowerCase()}:${value}`)
    .sort()
}

/** True when both refer to the same URL with the same headers: a renewed token is a change. */
export function sameSourceLocation(a: SnapshotSourceRef, b: SnapshotSourceRef): boolean {
  const left = toSourceLocation(a)
  const right = toSourceLocation(b)
  return (
    left.url === right.url &&
    (left.credentials ?? null) === (right.credentials ?? null) &&
    headerEntries(left).join('\n') === headerEntries(right).join('\n')
  )
}

export function hasSourceHeaders(location: SnapshotSourceLocation): boolean {
  return Object.keys(location.headers ?? {}).length > 0
}

/**
 * Browsers drop `Authorization` when a redirect leaves the origin (measured in Chromium for
 * fetch and sync XHR alike), so a failed answer from another origin than the one asked
 * cannot be fixed by a renewed token.
 */
export function redirectDroppedHeaders(
  location: SnapshotSourceLocation,
  finalUrl: string,
): boolean {
  if (!finalUrl || !hasSourceHeaders(location)) return false
  // A relative URL (a same-origin proxy) resolves against the worker's location.
  const base = (globalThis as { location?: { href: string } }).location?.href
  try {
    return new URL(finalUrl, base).origin !== new URL(location.url, base).origin
  } catch {
    return false
  }
}
