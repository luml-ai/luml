import axios from 'axios'

const fragment = new URLSearchParams(window.location.hash.slice(1))
const sessionToken = fragment.get('session-token')
if (sessionToken) {
  sessionStorage.setItem('flow-session-token', sessionToken)
  window.history.replaceState(null, '', window.location.pathname + window.location.search)
}

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('flow-session-token')
  if (token) config.headers.set('Authorization', `Bearer ${token}`)
  return config
})
