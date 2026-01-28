import axios from 'axios'

export const api = axios.create({
  baseURL: import.meta.env.DEV ? '' : '',
  headers: {
    'Content-Type': 'application/json',
  },
})
