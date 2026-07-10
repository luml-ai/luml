import type { ForecastingAggregation, ForecastingFrequency } from './interfaces'

export interface ForecastSetupConfig {
  date_col: string
  target_col: string
  aux_cols: string[]
  known_future_cols: string[]
  frequency: ForecastingFrequency
  preview_horizon: number | null
  aggregation: ForecastingAggregation
}

const DATE_SAMPLE_SIZE = 25
const DATE_COLUMN_THRESHOLD = 0.7
const NUMERIC_STRING = /^[+-]?\d+(\.\d+)?$/

/**
 * A value is treated as a date when it is a valid `Date` (arquero auto-types
 * ISO columns to `Date`) or a non-numeric string that `Date.parse` accepts.
 * Bare numbers are rejected so numeric feature columns are never mistaken for
 * dates (e.g. a 4-digit sales value would otherwise parse as a year).
 */
export function isDateLike(value: unknown): boolean {
  if (value instanceof Date) return !Number.isNaN(value.getTime())
  if (typeof value !== 'string') return false
  const trimmed = value.trim()
  if (!trimmed || NUMERIC_STRING.test(trimmed)) return false
  return !Number.isNaN(Date.parse(trimmed))
}

const ISO_DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/
const EXPLICIT_UTC_OFFSET = /(?:Z|[+-]\d{2}:\d{2})$/i
const MS_PER_DAY = 86_400_000

function utcDayFromLocal(date: Date): Date {
  return new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()))
}

/**
 * UTC midnight of the calendar day `date` represents. Exact UTC midnights
 * (ISO-parsed date-only values) pass through; anything else — notably the
 * local-midnight Dates the DatePicker produces — is read in local time so the
 * day the user saw survives regardless of the runtime timezone.
 */
export function toUtcDay(date: Date): Date {
  return date.getTime() % MS_PER_DAY === 0 ? date : utcDayFromLocal(date)
}

/**
 * All downstream arithmetic (`periodsBetween`/`periodKey`/`forecastDate`) is
 * UTC, but `Date.parse` reads only date-only ISO strings as UTC — non-ISO
 * strings ("02/01/2020") and offset-less date-times parse in *local* time, so
 * they must be re-anchored to UTC midnight or a date near a period boundary
 * shifts a period in non-UTC browsers.
 */
function toDate(value: unknown): Date | null {
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : toUtcDay(value)
  if (typeof value !== 'string') return null
  const trimmed = value.trim()
  if (!trimmed || NUMERIC_STRING.test(trimmed)) return null
  const ms = Date.parse(trimmed)
  if (Number.isNaN(ms)) return null
  const parsed = new Date(ms)
  if (ISO_DATE_ONLY.test(trimmed)) return parsed
  if (EXPLICIT_UTC_OFFSET.test(trimmed)) {
    return new Date(Date.UTC(parsed.getUTCFullYear(), parsed.getUTCMonth(), parsed.getUTCDate()))
  }
  return utcDayFromLocal(parsed)
}

/** True when a strong majority of the column's sampled values look like dates. */
export function isDateColumn(rows: Record<string, unknown>[], column: string): boolean {
  const sample = rows.slice(0, DATE_SAMPLE_SIZE)
  const present = sample.filter((row) => {
    const value = row[column]
    return value !== null && value !== undefined && value !== ''
  })
  if (!present.length) return false
  const dateLike = present.filter((row) => isDateLike(row[column])).length
  return dateLike / present.length >= DATE_COLUMN_THRESHOLD
}

export function detectDateColumns(rows: Record<string, unknown>[], columns: string[]): string[] {
  return columns.filter((column) => isDateColumn(rows, column))
}

function isNumericValue(value: unknown): boolean {
  if (typeof value === 'number') return Number.isFinite(value)
  if (typeof value !== 'string') return false
  const trimmed = value.trim()
  return trimmed !== '' && Number.isFinite(Number(trimmed))
}

/**
 * True when a strong majority of the column's sampled values are numbers,
 * mirroring the engine's `pd.to_numeric` coercion of the target: a mostly
 * non-numeric target would only fail server-side with an opaque
 * "not enough data" error after dropping the unparseable rows.
 */
export function isNumericColumn(rows: Record<string, unknown>[], column: string): boolean {
  const sample = rows.slice(0, DATE_SAMPLE_SIZE)
  const present = sample.filter((row) => {
    const value = row[column]
    return value !== null && value !== undefined && value !== ''
  })
  if (!present.length) return false
  const numeric = present.filter((row) => isNumericValue(row[column])).length
  return numeric / present.length >= DATE_COLUMN_THRESHOLD
}

/** The most recent parseable date in `column`, or `null` when none parse. */
export function lastDate(rows: Record<string, unknown>[], column: string): Date | null {
  let latest: Date | null = null
  for (const row of rows) {
    const date = toDate(row[column])
    if (date && (!latest || date > latest)) latest = date
  }
  return latest
}

function periodOrdinal(date: Date, frequency: 'month' | 'quarter' | 'year'): number {
  const year = date.getUTCFullYear()
  switch (frequency) {
    case 'month':
      return year * 12 + date.getUTCMonth()
    case 'quarter':
      return year * 4 + Math.floor(date.getUTCMonth() / 3)
    case 'year':
      return year
  }
}

/**
 * Number of forecast periods between the last history date and a chosen future
 * end date, at the model frequency. Month/quarter/year count calendar-period
 * boundaries crossed (mirroring the engine's period-start snapping), so the
 * result is independent of either date's day within its period; day/week count
 * fixed steps, rounding partial weeks up. Returns 0 when `end` is not after
 * `from`; otherwise at least 1 so the horizon reaches the selected date.
 */
export function periodsBetween(from: Date, end: Date, frequency: ForecastingFrequency): number {
  const fromDay = toUtcDay(from)
  const endDay = toUtcDay(end)
  if (endDay.getTime() <= fromDay.getTime()) return 0
  switch (frequency) {
    case 'day':
      return Math.round((endDay.getTime() - fromDay.getTime()) / MS_PER_DAY)
    case 'week':
      return Math.ceil((endDay.getTime() - fromDay.getTime()) / (7 * MS_PER_DAY))
    case 'month':
    case 'quarter':
    case 'year':
      return Math.max(1, periodOrdinal(endDay, frequency) - periodOrdinal(fromDay, frequency))
  }
}

function formatUtcDate(date: Date): string {
  return date.toISOString().slice(0, 10)
}

/**
 * The i-th forecast date after `from`, replicating the engine's
 * `_generate_future_dates`: day/week advance by fixed offsets from the last
 * date, while month/quarter/year snap to the period start (first of the
 * month/quarter/year). All arithmetic is UTC so the ISO output is stable
 * regardless of the runtime timezone.
 */
function forecastDate(from: Date, step: number, frequency: ForecastingFrequency): Date {
  const year = from.getUTCFullYear()
  const month = from.getUTCMonth()
  switch (frequency) {
    case 'day':
      return new Date(from.getTime() + step * MS_PER_DAY)
    case 'week':
      return new Date(from.getTime() + step * 7 * MS_PER_DAY)
    case 'month':
      return new Date(Date.UTC(year, month + step, 1))
    case 'quarter':
      return new Date(Date.UTC(year, (Math.floor(month / 3) + step) * 3, 1))
    case 'year':
      return new Date(Date.UTC(year + step, 0, 1))
  }
}

/**
 * The `horizon` consecutive forecast dates (`YYYY-MM-DD`) beyond `from`. These
 * must match the dates the engine generates so a future-values grid built from
 * them aligns with the model's predict-time validation.
 */
export function generateForecastDates(
  from: Date,
  horizon: number,
  frequency: ForecastingFrequency,
): string[] {
  return Array.from({ length: Math.max(0, horizon) }, (_, i) =>
    formatUtcDate(forecastDate(from, i + 1, frequency)),
  )
}

/**
 * A canonical key identifying which forecast period a date falls in, used to
 * match uploaded CSV rows to the horizon grid. Mirrors the engine's
 * period-based `future` validation (exact date for day/week; year-month,
 * year-quarter, or year for the coarser frequencies).
 */
export function periodKey(value: unknown, frequency: ForecastingFrequency): string | null {
  const date = toDate(value)
  if (!date) return null
  const year = date.getUTCFullYear()
  const month = date.getUTCMonth()
  switch (frequency) {
    case 'day':
    case 'week':
      return formatUtcDate(date)
    case 'month':
      return `${year}-${String(month + 1).padStart(2, '0')}`
    case 'quarter':
      return `${year}-Q${Math.floor(month / 3) + 1}`
    case 'year':
      return `${year}`
  }
}
