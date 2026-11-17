import { seededRandom, type MetricPoint } from './metricDatabases'

const SPECIAL_VALUES = [null, Infinity, -Infinity]

/**
 * Several keys of different lengths with overwritten, sparse and negative steps, NULL (NaN)
 * and +-inf values, in the order a training loop would log them.
 */
export function generatedMetrics(seed = 7): MetricPoint[] {
  const random = seededRandom(seed)
  const points: MetricPoint[] = []
  const integer = (low: number, high: number) => low + Math.floor(random() * (high - low + 1))

  for (let step = 0; step < 3000; step++) {
    points.push({ key: 'loss', step, value: 2 / (1 + step) + random() * 0.01 })
  }
  for (let index = 0; index < 300; index++) {
    points.push({ key: 'loss', step: integer(0, 2999), value: random() - 0.5 })
  }
  for (let index = 0; index < 400; index++) {
    points.push({ key: 'eval/accuracy', step: integer(-50_000, 200_000), value: random() })
  }
  for (let step = -5000; step < 0; step += 7) {
    points.push({ key: 'warmup', step, value: (random() - 0.5) * 1e6 })
  }
  for (let step = 0; step < 600; step++) {
    const special = random() < 0.4
    const value = special ? (SPECIAL_VALUES[integer(0, 2)] ?? null) : random() * 10 - 5
    points.push({ key: 'unstable', step: step * 3, value })
  }
  for (let step = 1000; step < 1064; step++) {
    points.push({ key: 'unstable', step, value: null })
  }
  points.push({ key: 'single', step: 123_456_789, value: 42 })
  // Beyond the summable limit: in count, min and max, never in finite_count or sum.
  for (let step = 0; step < 3; step++) points.push({ key: 'overflow', step, value: 1.5e308 })
  points.push({ key: 'overflow', step: 3, value: -1e300 })
  points.push({ key: 'overflow', step: 4, value: 1e290 })
  points.push({ key: 'overflow', step: 70, value: -1 })
  for (let index = 0; index < 4000; index++) {
    points.push({ key: 'long/run', step: index * 1237 - 100_000, value: Math.sin(index) * 100 })
  }
  return points
}

export const GENERATED_KEYS = [
  'eval/accuracy',
  'long/run',
  'loss',
  'overflow',
  'single',
  'unstable',
  'warmup',
]

/** Sub-ranges with unaligned, negative, one-sided and empty bounds. */
export const SUB_RANGES: [number | null, number | null][] = [
  [null, null],
  [-1000, 1000],
  [100, 2500],
  [-60_000, -10],
  [1500, null],
  [null, 0],
  [123_456_789, 123_456_789],
  [1_000_000_000, 2_000_000_000],
]
