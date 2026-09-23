import { describe, expect, it } from 'vitest'
import { getErrorMessage } from './helpers'

describe('getErrorMessage', () => {
  it('preserves string API details and standard error messages', () => {
    expect(getErrorMessage({ response: { data: { detail: 'Artifact not found' } } })).toBe(
      'Artifact not found',
    )
    expect(getErrorMessage(new Error('Network error'))).toBe('Network error')
  })

  it('extracts messages from FastAPI validation errors', () => {
    const error = {
      response: {
        data: {
          detail: [
            {
              type: 'uuid_parsing',
              loc: ['path', 'artifact_id'],
              msg: 'Input should be a valid UUID',
              input: 'abc',
            },
          ],
        },
      },
    }

    expect(getErrorMessage(error, 'Failed to set current artifact')).toBe(
      'Input should be a valid UUID',
    )
  })

  it('joins multiple validation messages', () => {
    const error = {
      response: {
        data: {
          detail: [{ msg: 'First validation error' }, { msg: 'Second validation error' }],
        },
      },
    }

    expect(getErrorMessage(error)).toBe('First validation error; Second validation error')
  })

  it('uses the fallback when structured details have no message', () => {
    const error = { response: { data: { detail: { type: 'uuid_parsing' } } } }

    expect(getErrorMessage(error, 'Failed to set current artifact')).toBe(
      'Failed to set current artifact',
    )
  })
})
