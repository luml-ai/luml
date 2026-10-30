import { ref } from 'vue'

const SESSION_TOKEN_KEY = 'flow-session-token'

export const sessionTokenRejected = ref(false)

export const page = {
  reload: () => window.location.reload(),
}

export function getSessionToken() {
  return localStorage.getItem(SESSION_TOKEN_KEY)
}

export function saveSessionToken(token: string) {
  localStorage.setItem(SESSION_TOKEN_KEY, token)
  sessionTokenRejected.value = false
}

export function takeSessionTokenFromFragment() {
  const token = new URLSearchParams(window.location.hash.slice(1)).get('session-token')
  if (!token) return false
  saveSessionToken(token)
  window.history.replaceState(null, '', window.location.pathname + window.location.search)
  return true
}
