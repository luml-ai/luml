
import { ref } from 'vue'
import type { Ref } from 'vue'

export const TOKEN_PARAM = 'token'
export const TOKEN_STORAGE_KEY = 'lumlflow.flow.token'
export const DAEMON_LOG_PARAM = 'log'
export const DAEMON_LOG_STORAGE_KEY = 'lumlflow.flow.daemon-log'

export interface TokenSource {
  search: string
  storage: Pick<Storage, 'getItem' | 'setItem'>
  previous?: Pick<Storage, 'getItem'>
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
  if (token !== null) rejected.value = false
  return token
}

export function browserDaemonLog(): string | null {
  if (typeof window === 'undefined') return null
  const offered = new URLSearchParams(window.location.search).get(DAEMON_LOG_PARAM)
  if (offered) window.localStorage.setItem(DAEMON_LOG_STORAGE_KEY, offered)
  return offered ?? window.localStorage.getItem(DAEMON_LOG_STORAGE_KEY)
}
