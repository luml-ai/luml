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
}

export function takeSessionTokenFromFragment() {
  const token = new URLSearchParams(window.location.hash.slice(1)).get('session-token')
  if (!token) return false
  saveSessionToken(token)
  window.history.replaceState(null, '', window.location.pathname + window.location.search)
  return true
}

export function tokenFromLaunchInput(value: string) {
  const input = value.trim()
  if (!input) return null
  const fragmentStart = input.indexOf('#')
  if (fragmentStart !== -1) {
    return new URLSearchParams(input.slice(fragmentStart + 1)).get('session-token')
  }
  if (input.includes('://') || /\s/.test(input)) return null
  return input
}
