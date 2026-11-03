import { describe, expect, it } from 'vitest'
import { durationToText } from '@/helpers/date'

describe('a run duration, given in seconds as the tracker stores it', () => {
  it.each([
    [0.8019670844078064, '802ms'],
    [0.0004, '0ms'],
    [1, '1s'],
    [12.345, '12.3s'],
    [59.96, '60s'],
    [60, '1m'],
    [300, '5m'],
    [125.4, '2m 5s'],
    [3600, '1h'],
    [5400, '1h 30m'],
    [90000, '1d 1h'],
    [172800, '2d'],
  ])('%s s reads %s', (seconds, text) => {
    expect(durationToText(seconds)).toBe(text)
  })

  it('shows a dash for a value it cannot read', () => {
    expect(durationToText(Number.NaN)).toBe('-')
    expect(durationToText(-1)).toBe('-')
  })
})
