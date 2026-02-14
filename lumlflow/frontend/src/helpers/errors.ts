import { AxiosError } from 'axios'

export const getErrorMessage = (error: unknown, defaultMessage = 'Unknown error') => {
  if (error instanceof AxiosError) return error.response?.data?.detail || error.message
  if (error instanceof Error) return error.message
  return defaultMessage
}
