import axios from 'axios'

// The served app talks to its own origin: `lumlflow ui` puts the tracker's
// routers and these static files on one port, so a same-origin `/api` is the
// address. An explicit VITE_API_URL still wins, for a build pointed elsewhere.
export const API_BASE_URL = import.meta.env.VITE_API_URL ?? '/api'

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})
