import type { ForecastPoint, ForecastPredictedRecord } from './interfaces'

const PREDICTED_PREFIX = 'predicted_'

/**
 * Pivot the wide `predicted_<col>` records returned by `/forecasting/predict`
 * into per-series points keyed by column name. The target series carries its
 * 95% prediction interval (`predicted_<target>_lower`/`_upper`); auxiliary
 * series are point-only. Knowing `targetCol` disambiguates the target's bound
 * columns from an auxiliary whose name happens to end in `_lower`/`_upper`.
 */
export function normalizeForecastRecords(
  records: ForecastPredictedRecord[],
  dateCol: string,
  targetCol: string,
): Record<string, ForecastPoint[]> {
  const targetMeanKey = `${PREDICTED_PREFIX}${targetCol}`
  const targetLowerKey = `${targetMeanKey}_lower`
  const targetUpperKey = `${targetMeanKey}_upper`
  const series: Record<string, ForecastPoint[]> = {}

  const push = (col: string, point: ForecastPoint): void => {
    const points = series[col] ?? (series[col] = [])
    points.push(point)
  }

  for (const record of records) {
    const date = String(record[dateCol])

    if (targetMeanKey in record) {
      const point: ForecastPoint = { date, value: Number(record[targetMeanKey]) }
      if (targetLowerKey in record) point.lower = Number(record[targetLowerKey])
      if (targetUpperKey in record) point.upper = Number(record[targetUpperKey])
      push(targetCol, point)
    }

    for (const key of Object.keys(record)) {
      if (
        key === dateCol ||
        key === targetMeanKey ||
        key === targetLowerKey ||
        key === targetUpperKey ||
        !key.startsWith(PREDICTED_PREFIX)
      ) {
        continue
      }
      push(key.slice(PREDICTED_PREFIX.length), { date, value: Number(record[key]) })
    }
  }

  return series
}
