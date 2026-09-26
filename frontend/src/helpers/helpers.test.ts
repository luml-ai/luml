import { describe, expect, it } from 'vitest'
import { getErrorDetail, getErrorMessage, getSizeText } from './helpers'

describe('getSizeText', () => {
  it.each([
    [0, '0.00 B'],
    [999, '999.00 B'],
    [1000, '1.00 KB'],
    [999994, '999.99 KB'],
    [999995, '1.00 MB'],
    [999999, '1.00 MB'],
    [1000000, '1.00 MB'],
    [250000000, '250.00 MB'],
    [999999999, '1.00 GB'],
    [1000000000, '1.00 GB'],
    [1700000000, '1.70 GB'],
    [100000000000, '100.00 GB'],
    [999999999999, '1.00 TB'],
    [1500000000000, '1.50 TB'],
    [5000000000000, '5.00 TB'],
    [2000000000000000, '2000.00 TB'],
  ])('formats %i bytes as %s', (size, expected) => {
    expect(getSizeText(size)).toBe(expected)
  })
})

describe('getErrorDetail', () => {
  it('returns a string detail as is', () => {
    expect(getErrorDetail('Collection not found')).toBe('Collection not found')
  })

  it('formats a FastAPI validation error list with field names', () => {
    expect(
      getErrorDetail([
        {
          type: 'string_too_long',
          loc: ['body', 'description'],
          msg: 'String should have at most 1000 characters',
        },
        {
          type: 'string_too_long',
          loc: ['body', 'tags', 0],
          msg: 'String should have at most 64 characters',
        },
      ]),
    ).toBe(
      'description should have at most 1000 characters; tags.0 should have at most 64 characters',
    )
  })

  it('names the missing field', () => {
    expect(getErrorDetail([{ loc: ['body', 'name'], msg: 'Field required' }])).toBe(
      'name is required',
    )
  })

  it('prefixes a custom message that does not mention the field', () => {
    expect(
      getErrorDetail([
        { loc: ['body', 'tags'], msg: 'Value error, duplicate tags are not allowed' },
      ]),
    ).toBe('tags: duplicate tags are not allowed')
  })

  it('keeps only the message when the error is not tied to a field', () => {
    expect(getErrorDetail([{ loc: ['body'], msg: 'Field required' }])).toBe('Field required')
  })

  it('reads the message of an object detail', () => {
    expect(getErrorDetail({ message: 'Quota exceeded' })).toBe('Quota exceeded')
  })

  it.each([undefined, null, '', [], [{ loc: ['body', 'name'] }], { code: 1 }])(
    'returns undefined for %j',
    (detail) => {
      expect(getErrorDetail(detail)).toBeUndefined()
    },
  )
})

describe('getErrorMessage', () => {
  it('never renders a validation error list as [object Object]', () => {
    const error = {
      message: 'Request failed with status code 422',
      response: {
        data: { detail: [{ loc: ['body', 'name'], msg: 'Value error, name must not be empty' }] },
      },
    }

    expect(getErrorMessage(error)).toBe('name must not be empty')
  })

  it('falls back to the error message and then to the default', () => {
    expect(getErrorMessage({ message: 'Network Error' })).toBe('Network Error')
    expect(getErrorMessage({}, 'Failed to update collection')).toBe('Failed to update collection')
  })
})
