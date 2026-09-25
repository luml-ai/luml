/**
 * How the tab comes by the workspace's daemon token.
 *
 * The static files are served without one — they are the client that is about
 * to present it — so `lumlflow ui` opens the SPA with `?token=` in the URL and
 * this reads it once. It is then kept in storage and taken back out of the
 * address bar: a token left there is a token that ends up in a bookmark, a
 * screenshot, or the next person's shoulder, and every later navigation would
 * carry it for no reader.
 *
 * Local storage, not session: a token that outlives the tab can be a stale one,
 * but a stale token has a surface — the daemon answers 401, `rejectToken` drops
 * it, and the tab says it is not connected — while a token dropped with the tab
 * costs a working key on every browser restart and in every second tab, which
 * is a working setup broken by the clock. Storage is per origin, so the keys
 * `127.0.0.1` holds are not the ones `localhost` holds: the address `lumlflow
 * ui` prints is the one that has it.
 */

import { ref } from 'vue'
import type { Ref } from 'vue'

export const TOKEN_PARAM = 'token'
export const TOKEN_STORAGE_KEY = 'lumlflow.flow.token'
export const DAEMON_LOG_PARAM = 'log'
export const DAEMON_LOG_STORAGE_KEY = 'lumlflow.flow.daemon-log'

export interface TokenSource {
  /** `window.location.search`, or whatever a test hands in. */
  search: string
  storage: Pick<Storage, 'getItem' | 'setItem'>
  /** Where earlier builds kept it; read once so an open tab is not logged out. */
  previous?: Pick<Storage, 'getItem'>
  /** Called with the URL to keep once the token has been taken out of it. */
  strip?: (url: string) => void
}

export function resolveToken(source: TokenSource): string | null {
  const params = new URLSearchParams(source.search)
  const offered = params.get(TOKEN_PARAM)
  if (!offered) return source.storage.getItem(TOKEN_STORAGE_KEY) ?? adopt(source)
  source.storage.setItem(TOKEN_STORAGE_KEY, offered)
  params.delete(TOKEN_PARAM)
  const rest = params.toString()
  source.strip?.(rest ? `?${rest}` : '')
  return offered
}

function adopt(source: TokenSource): string | null {
  const held = source.previous?.getItem(TOKEN_STORAGE_KEY) ?? null
  if (held !== null) source.storage.setItem(TOKEN_STORAGE_KEY, held)
  return held
}

/**
 * The token this tab holds, after the daemon refused it. One token per tab, so
 * one fact: every surface that reports "not connected" reads this rather than
 * deciding it from whichever call happened to fail in front of it.
 */
const rejected = ref(false)
export const tokenRejected: Readonly<Ref<boolean>> = rejected

/**
 * The daemon does not accept this token — a restarted `lumlflow ui` mints a new
 * one. Keeping it would mean every later gesture failing with a sentence no
 * reader can act on, so it goes, from both storages: leaving the session copy
 * would only have the next read adopt the dead token back.
 */
export function rejectToken(): void {
  rejected.value = true
  if (typeof window === 'undefined') return
  window.localStorage.removeItem(TOKEN_STORAGE_KEY)
  window.sessionStorage.removeItem(TOKEN_STORAGE_KEY)
}

/** The browser's own answer to the same question. */
export function browserToken(): string | null {
  if (typeof window === 'undefined') return null
  browserDaemonLog()
  const token = resolveToken({
    search: window.location.search,
    storage: window.localStorage,
    previous: window.sessionStorage,
    strip: (query) =>
      window.history.replaceState(
        window.history.state,
        '',
        `${window.location.pathname}${query}${window.location.hash}`,
      ),
  })
  // A token in hand is one nothing has refused: the refused one was removed.
  if (token !== null) rejected.value = false
  return token
}

export function browserDaemonLog(): string | null {
  if (typeof window === 'undefined') return null
  const offered = new URLSearchParams(window.location.search).get(DAEMON_LOG_PARAM)
  if (offered) window.localStorage.setItem(DAEMON_LOG_STORAGE_KEY, offered)
  return offered ?? window.localStorage.getItem(DAEMON_LOG_STORAGE_KEY)
}
