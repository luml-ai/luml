/** An inclusive range of integers `[start, end]`. */
export type Interval = readonly [start: number, end: number]

/** A set of integers kept as sorted, disjoint, non-adjacent inclusive intervals. */
export class IntervalSet {
  private ranges: Interval[] = []

  get intervals(): readonly Interval[] {
    return this.ranges
  }

  get isEmpty(): boolean {
    return this.ranges.length === 0
  }

  add(start: number, end: number): void {
    if (start > end) return
    const kept: Interval[] = []
    let mergedStart = start
    let mergedEnd = end
    for (const [rangeStart, rangeEnd] of this.ranges) {
      if (rangeEnd + 1 < mergedStart || rangeStart > mergedEnd + 1) {
        kept.push([rangeStart, rangeEnd])
      } else {
        mergedStart = Math.min(mergedStart, rangeStart)
        mergedEnd = Math.max(mergedEnd, rangeEnd)
      }
    }
    kept.push([mergedStart, mergedEnd])
    this.ranges = kept.sort((left, right) => left[0] - right[0])
  }

  /** Removes every member from `start` on. */
  removeFrom(start: number): void {
    this.ranges = this.ranges
      .filter(([rangeStart]) => rangeStart < start)
      .map(([rangeStart, rangeEnd]) => [rangeStart, Math.min(rangeEnd, start - 1)] as const)
  }

  /** The parts of `[start, end]` not in the set, in ascending order. */
  missing(start: number, end: number): Interval[] {
    const gaps: Interval[] = []
    let cursor = start
    for (const [rangeStart, rangeEnd] of this.ranges) {
      if (cursor > end) break
      if (rangeEnd < cursor) continue
      if (rangeStart > cursor) gaps.push([cursor, Math.min(rangeStart - 1, end)])
      cursor = Math.max(cursor, rangeEnd + 1)
    }
    if (cursor <= end) gaps.push([cursor, end])
    return gaps
  }

  covers(start: number, end: number): boolean {
    return start > end || this.missing(start, end).length === 0
  }
}
