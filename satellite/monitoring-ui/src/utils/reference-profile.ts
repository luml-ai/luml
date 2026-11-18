import { SectionState, type ReferenceProfileResponse } from '@/api/monitoring/interfaces'
import { JSON_ARRAY_PREVIEW_LIMIT } from '@/constants/reference-profile'
import type { EmptyStateContent } from '@/types/empty'
import {
  JsonValueKind,
  type JsonEntry,
  type ReferenceProfileSummaryItem,
} from '@/types/reference-profile'
import { formatInteger } from '@/utils/format'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function getPath(source: unknown, path: string[]): unknown {
  return path.reduce<unknown>(
    (current, key) => (isRecord(current) ? current[key] : undefined),
    source,
  )
}

function countKeys(value: unknown): number {
  return isRecord(value) ? Object.keys(value).length : 0
}

function toText(value: unknown): string {
  if (typeof value === 'string' && value) return value
  if (typeof value === 'number') return formatInteger(value)
  return '—'
}

export function getReferenceProfileSummary(
  profile: ReferenceProfileResponse,
): ReferenceProfileSummaryItem[] {
  const document = profile.document
  const summaries = getPath(document, ['feature_summaries'])
  const categorical = countKeys(getPath(summaries, ['categorical_features']))
  const numerical = countKeys(getPath(summaries, ['numerical_features']))
  return [
    { label: 'Status', value: profile.profile_status },
    { label: 'Task type', value: toText(getPath(document, ['task_type'])) },
    {
      label: 'Features',
      value: isRecord(summaries) ? `${categorical} categorical · ${numerical} numerical` : '—',
    },
    {
      label: 'PCA components',
      value: toText(getPath(document, ['pca_profile', 'pca', 'n_components'])),
    },
    { label: 'Monitored output', value: toText(getPath(document, ['output_summary', 'name'])) },
  ]
}

export function formatReferenceDocument(document: Record<string, unknown>): string {
  return JSON.stringify(document, null, 2)
}

export function formatLinesCount(text: string): string {
  const count = text.split('\n').length
  return `${formatInteger(count)} ${count === 1 ? 'line' : 'lines'}`
}

export function isJsonPrimitiveArray(value: unknown): value is unknown[] {
  return (
    Array.isArray(value) &&
    value.length > 0 &&
    value.every((item) => item === null || typeof item !== 'object')
  )
}

export function isJsonBranch(value: unknown): boolean {
  return value !== null && typeof value === 'object' && !isJsonPrimitiveArray(value)
}

export function getJsonEntries(value: unknown): JsonEntry[] {
  if (Array.isArray(value)) return value.map((item, index) => ({ key: String(index), value: item }))
  if (isRecord(value)) return Object.entries(value).map(([key, item]) => ({ key, value: item }))
  return []
}

export function getJsonBadge(value: unknown): string {
  const count = getJsonEntries(value).length
  return Array.isArray(value) ? `[${count}]` : `{${count}}`
}

function formatJsonPrimitive(value: unknown): string {
  if (value === null) return 'null'
  if (typeof value === 'string') return `"${value}"`
  if (typeof value === 'number') return String(Number(value.toFixed(6)))
  return String(value)
}

export function formatJsonLeaf(value: unknown): string {
  if (!isJsonPrimitiveArray(value)) return formatJsonPrimitive(value)
  const head = value.slice(0, JSON_ARRAY_PREVIEW_LIMIT).map(formatJsonPrimitive).join(', ')
  return value.length > JSON_ARRAY_PREVIEW_LIMIT ? `[${head}, …] (${value.length})` : `[${head}]`
}

export function getJsonValueKind(value: unknown): JsonValueKind {
  if (typeof value === 'number') return JsonValueKind.NUMBER
  if (typeof value === 'string') return JsonValueKind.STRING
  return JsonValueKind.MUTED
}

export function getReferenceProfileEmptyState(
  profile: ReferenceProfileResponse,
): EmptyStateContent | null {
  if (profile.state === SectionState.UNAVAILABLE) {
    return {
      title: 'Reference profile unavailable',
      detail: 'The monitoring store could not provide the reference profile.',
    }
  }
  if (profile.state === SectionState.EMPTY || !profile.document) {
    return {
      title: 'No reference profile yet',
      detail: 'Attach a reference profile to the model to compare live traffic against training.',
    }
  }
  return null
}
