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

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
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
