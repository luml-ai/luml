const STORAGE_KEY = 'auth-redirect'

export function getSafeAuthRedirect(value: unknown): string | undefined {
  const candidate = Array.isArray(value) ? value[0] : value
  if (typeof candidate !== 'string' || !candidate.startsWith('/') || candidate.startsWith('//')) {
    return undefined
  }

  try {
    const url = new URL(candidate, window.location.origin)
    if (url.origin !== window.location.origin) return undefined
    return `${url.pathname}${url.search}${url.hash}`
  } catch {
    return undefined
  }
}

export function storeAuthRedirect(value: unknown) {
  const redirect = getSafeAuthRedirect(value)
  if (redirect) localStorage.setItem(STORAGE_KEY, redirect)
  else localStorage.removeItem(STORAGE_KEY)
}

export function getStoredAuthRedirect() {
  return getSafeAuthRedirect(localStorage.getItem(STORAGE_KEY))
}

export function clearStoredAuthRedirect() {
  localStorage.removeItem(STORAGE_KEY)
}
