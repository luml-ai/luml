import { describe, expect, it } from 'vitest'
import { combineValidators, getSatelliteValidator } from '@/helpers/helpers'

describe('satellite field validation', () => {
  it.each([null, undefined, ''])('treats an empty optional field as absent: %s', (value) => {
    const validator = combineValidators([getSatelliteValidator({ type: 'min', value: 1 })], false)

    expect(validator.safeParse(value).success).toBe(true)
  })

  it('still validates a populated optional field', () => {
    const validator = combineValidators([getSatelliteValidator({ type: 'min', value: 1 })], false)

    expect(validator.safeParse(0).success).toBe(false)
    expect(validator.safeParse(1).success).toBe(true)
  })

  it('uses wire-format regex strings and validator messages', () => {
    const validator = getSatelliteValidator({
      type: 'regex',
      value: '^https://',
      message: 'Use HTTPS',
    })
    const result = validator.safeParse('http://example.com')

    expect(result.success).toBe(false)
    if (!result.success) expect(result.error.issues[0]?.message).toBe('Use HTTPS')
  })
})
