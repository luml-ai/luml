import { describe, expect, it } from 'vitest'
import { autoDeclinedText } from '@/components/notebooks/cell/autoDeclined'

describe('why a stale cell was left for the user', () => {
  it('says nothing when reactivity did not decline it', () => {
    expect(autoDeclinedText(null, 5)).toBe('')
    expect(autoDeclinedText(undefined, 5)).toBe('')
  })

  it('names the cost and the limit for an expensive cell', () => {
    expect(
      autoDeclinedText({ reason: 'too-expensive', estimate_seconds: 42.4, untimed: [] }, 5),
    ).toBe(
      'Not refreshed automatically: takes about 42 s, over the 5 s auto limit. Run it when ready.',
    )
  })

  it('names the cells that were never timed', () => {
    expect(
      autoDeclinedText(
        { reason: 'never-timed', estimate_seconds: 0, untimed: ['features', 'train'] },
        5,
      ),
    ).toBe(
      'Not refreshed automatically: `features`, `train` never ran here, so the cost is unknown. Run it once.',
    )
  })

  it("passes the daemon's own reason through for the rest", () => {
    expect(
      autoDeclinedText(
        {
          reason: 'dangling-experiment',
          estimate_seconds: 0,
          untimed: [],
          detail: '`retrieval_eval` must run because its unreachable experiment is needed.',
        },
        5,
      ),
    ).toBe(
      'Not refreshed automatically: `retrieval_eval` must run because its unreachable experiment is needed.',
    )
  })
})
