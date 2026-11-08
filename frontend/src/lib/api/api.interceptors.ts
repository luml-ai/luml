import type { AxiosInstance } from 'axios'

export const installInterceptors = (api: AxiosInstance) => {
  let refreshRequest: Promise<unknown> | undefined
  let logoutDispatched = false

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
        !originalRequest.skipInterceptors &&
        (!originalRequest.sessionCheck ||
          error.response.data?.detail === 'Session refresh required')
      ) {
        originalRequest._retry = true

        if (!refreshRequest) {
          logoutDispatched = false
          refreshRequest = api
            .post(
              '/v1/auth/refresh',
              {},
              {
                skipInterceptors: true,
                withCredentials: true,
              },
            )
            .finally(() => {
              refreshRequest = undefined
            })
        }

        try {
          await refreshRequest
        } catch (refreshError) {
          if (!originalRequest.sessionCheck && !logoutDispatched) {
            logoutDispatched = true
            console.error('Token refresh failed, logging out')
            window.dispatchEvent(new CustomEvent('auth:logout'))
          }

          return Promise.reject(refreshError)
        }

        return api.request(originalRequest)
      }
      return Promise.reject(error)
    },
  )
}
