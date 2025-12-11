import { ApiClass } from './api'

declare module 'axios' {
  export interface AxiosRequestConfig {
    skipInterceptors?: boolean
  }
}

export const api = new ApiClass()
