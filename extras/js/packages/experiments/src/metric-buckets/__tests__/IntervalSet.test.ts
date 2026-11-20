import { describe, expect, it } from 'vitest'
import { IntervalSet, type Interval } from '../IntervalSet'
import { seededRandom } from '@/providers/__tests__/helpers/metricDatabases'

function runsOf(members: Set<number>, start: number, end: number, inside: boolean): Interval[] {
  const runs: [number, number][] = []
  for (let value = start; value <= end; value++) {
    if (members.has(value) !== inside) continue
    const last = runs.at(-1)
    if (last && last[1] === value - 1) last[1] = value
    else runs.push([value, value])
  }
  return runs
}

describe('IntervalSet', () => {
  it('merges overlapping and adjacent ranges', () => {
    const set = new IntervalSet()
    set.add(10, 20)
    set.add(21, 25)
    set.add(-5, -1)
    set.add(0, 0)
    set.add(40, 50)

    expect(set.intervals).toEqual([
      [-5, 0],
      [10, 25],
      [40, 50],
    ])
    expect(set.missing(-10, 60)).toEqual([
      [-10, -6],
      [1, 9],
      [26, 39],
      [51, 60],
    ])
    expect(set.covers(12, 24)).toBe(true)
    expect(set.covers(12, 26)).toBe(false)
  })

  it('matches a brute-force set under seeded random operations', () => {
    const random = seededRandom(1234)
    const integer = (low: number, high: number) => low + Math.floor(random() * (high - low + 1))
    for (let round = 0; round < 200; round++) {
      const set = new IntervalSet()
      const members = new Set<number>()
      for (let operation = 0; operation < 25; operation++) {
        const start = integer(-60, 60)
        const end = start + integer(-3, 15)
        set.add(start, end)
        for (let value = start; value <= end; value++) members.add(value)

        expect(set.intervals).toEqual(runsOf(members, -80, 80, true))
        const queryStart = integer(-70, 70)
        const queryEnd = queryStart + integer(0, 40)
        expect(set.missing(queryStart, queryEnd)).toEqual(
          runsOf(members, queryStart, queryEnd, false),
        )
      }
    }
  })
})
