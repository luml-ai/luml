import { getErrorMessage } from '@/helpers/errors'

export const errorToast = (
  data: unknown,
  defaultDetail = 'Unknown error',
  summary = 'Error',
  life = 3000,
) => {
  const detail = getErrorMessage(data, defaultDetail)
  return {
    severity: 'error',
    summary: summary,
    detail: detail,
    life: life,
  }
}

export const successToast = (detail: string, summary = 'Success', life = 3000) => {
  return {
    severity: 'success',
    summary: summary,
    detail: detail,
    life: life,
  }
}
