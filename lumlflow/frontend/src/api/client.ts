import axios, { isAxiosError } from 'axios'
import {
  getSessionToken,
  page,
  sessionTokenRejected,
  takeSessionTokenFromFragment,
} from './session'

takeSessionTokenFromFragment()
window.addEventListener('hashchange', () => {
  if (takeSessionTokenFromFragment()) page.reload()
})

// The served app talks to its own origin: `lumlflow ui` puts the tracker's
// routers and these static files on one port, so a same-origin `/api` is the
// address. An explicit VITE_API_URL still wins for a build pointed elsewhere.
// The dev server is the exception: it proxies `/api` to the daemon itself (see
// vite.config.ts), so a stale `.env` pointing at another port must not win
// there — otherwise Experiments fails with a network error while the flow
// surface, which always uses the proxy, keeps working.
export const API_BASE_URL = import.meta.env.DEV ? '/api' : (import.meta.env.VITE_API_URL || '/api')

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.request.use((config) => {
  const token = getSessionToken()
  if (token) config.headers.set('Authorization', `Bearer ${token}`)
  return config
})

api.interceptors.response.use(undefined, (error) => {
  if (isAxiosError(error) && error.response?.status === 401) sessionTokenRejected.value = true
  return Promise.reject(error)
})
