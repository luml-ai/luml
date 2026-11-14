import { describe, expect, it } from 'vitest'
import { AxiosError } from 'axios'
import { getErrorMessage } from './errors'
import { errorToast } from '@/toasts'

describe('error messages', () => {
  it('preserves plain string errors in toasts', () => {
    expect(errorToast('Collection is empty').detail).toBe('Collection is empty')
  })
  it('preserves Error and AxiosError messages and unknown fallbacks', () => {
    expect(getErrorMessage(new Error('failed'))).toBe('failed')
    expect(getErrorMessage(new AxiosError('network failed'))).toBe('network failed')
    expect(getErrorMessage(null, 'fallback')).toBe('fallback')
  })
})
