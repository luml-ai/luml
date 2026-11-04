export const TOKEN_STORAGE_KEY = 'lumlflow.flow.token'

export function streamToken(): string | null {
  if (typeof window === 'undefined') return null
  return window.localStorage.getItem(TOKEN_STORAGE_KEY)
}
