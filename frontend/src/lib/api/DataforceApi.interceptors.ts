import type { AxiosInstance } from 'axios'

let isRefreshing = false
let failedQueue: Array<{
  resolve: (value?: any) => void
  reject: (reason?: any) => void
}> = []

const processQueue = (error: any = null) => {
  failedQueue.forEach((promise) => {
    if (error) {
      promise.reject(error)
    } else {
      promise.resolve()
    }
  })

  failedQueue = []
}

export const installDataforceInterceptors = (api: AxiosInstance) => {
  api.defaults.withCredentials = true
  api.interceptors.request.use(
    (config) => config,
    (error) => Promise.reject(error),
  )
  api.interceptors.response.use(
    (response) => response,
    async (error) => {
      const originalRequest = error.config

      if (
        error.response?.status === 401 &&
        !originalRequest._retry &&
        !originalRequest.url?.includes('/auth/refresh') &&
        !originalRequest.url?.includes('/auth/signin') &&
        !originalRequest.url?.includes('/auth/signup') &&
        !originalRequest.skipInterceptors
      ) {
        if (isRefreshing) {
          return new Promise((resolve, reject) => {
            failedQueue.push({ resolve, reject })
          })
            .then(() => api.request(originalRequest))
            .catch((err) => Promise.reject(err))
        }

        originalRequest._retry = true
        isRefreshing = true

        try {
          await api.post(
            '/auth/refresh',
            {},
            {
              skipInterceptors: true,
              withCredentials: true,
            },
          )

          processQueue()
          isRefreshing = false

          return api.request(originalRequest)
        } catch (refreshError) {
          processQueue(refreshError)
          isRefreshing = false
          console.error('Token refresh failed, logging out')
          window.dispatchEvent(new CustomEvent('auth:logout'))

          return Promise.reject(refreshError)
        }
      }
      return Promise.reject(error)
    },
  )
}
