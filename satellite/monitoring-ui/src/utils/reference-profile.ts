import {
  ProfileStatus,
  SectionState,
  type ReferenceProfileFeature,
  type ReferenceProfileResponse,
} from '@/api/monitoring/interfaces'
import { JSON_ARRAY_PREVIEW_LIMIT } from '@/constants/reference-profile'
import type { EmptyStateContent } from '@/types/empty'
import {
  JsonValueKind,
  type JsonEntry,
  type ReferenceNote,
  type ReferenceProbabilityItem,
  type ReferenceProfileSummaryItem,
  type ReferenceStatItem,
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

function getPcaComponents(document: unknown): unknown {
  const count = getPath(document, ['pca_profile', 'pca', 'n_components'])
  if (typeof count === 'number') return count
  const ratios = getPath(document, ['pca_profile', 'pca', 'explained_variance_ratio'])
  return Array.isArray(ratios) && ratios.length ? ratios.length : undefined
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
    { label: 'Reference rows', value: toText(getPath(document, ['n_reference_samples'])) },
    { label: 'PCA components', value: toText(getPcaComponents(document)) },
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

export function formatCharactersCount(text: string): string {
  const count = text.length
  return `${formatInteger(count)} ${count === 1 ? 'character' : 'characters'}`
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

const largeStatFormat = new Intl.NumberFormat('en-US', { maximumFractionDigits: 4 })
const smallStatFormat = new Intl.NumberFormat('en-US', { maximumSignificantDigits: 4 })

function formatStatValue(value: number): string {
  if (Number.isInteger(value)) return formatInteger(value)
  return Math.abs(value) >= 1 ? largeStatFormat.format(value) : smallStatFormat.format(value)
}

function formatProbability(value: number | null): string {
  return value == null ? '—' : `${(value * 100).toFixed(3)}%`
}

export function getReferenceStats(feature: ReferenceProfileFeature): ReferenceStatItem[] {
  return Object.entries(feature.summary).map(([label, value]) => ({
    label,
    value: formatStatValue(value),
  }))
}

function formatBinLabel(edges: number[], index: number): string {
  const from = edges[index]
  const to = edges[index + 1]
  return from == null || to == null
    ? String(index)
    : `${formatStatValue(from)} – ${formatStatValue(to)}`
}

function getProbabilityEntries(feature: ReferenceProfileFeature): [string, number | null][] {
  if (feature.categories?.length) {
    const probabilities = feature.category_probabilities ?? []
    return feature.categories.map((category, index) => [category, probabilities[index] ?? 0])
  }
  const histogram = feature.histogram ?? []
  const edges = feature.bin_edges ?? []
  if (!histogram.length) {
    return edges.slice(1).map((_, index) => [formatBinLabel(edges, index), null])
  }
  const total = histogram.reduce((sum, value) => sum + value, 0)
  return histogram.map((value, index) => [formatBinLabel(edges, index), total ? value / total : 0])
}

export function getReferenceProbabilities(
  feature: ReferenceProfileFeature,
): ReferenceProbabilityItem[] {
  return getProbabilityEntries(feature).map(([label, probability]) => ({
    label,
    value: formatProbability(probability),
    width: `${Math.min(100, Math.max(0, (probability ?? 0) * 100))}%`,
  }))
}

export function getReferenceProbabilitiesTitle(feature: ReferenceProfileFeature): string {
  return feature.categories?.length
    ? 'Reference category probabilities'
    : 'Reference bin probabilities'
}

function getReferenceNoteDetail(feature: ReferenceProfileFeature): string {
  return feature.categories?.length
    ? "Each logged batch is split into these categories and its category shares are compared against the reference probabilities to compute the feature's PSI drift score."
    : "Each logged batch is binned with these edges and compared against the reference probabilities to compute the feature's PSI drift score."
}

export function getReferenceNote(
  profile: ReferenceProfileResponse,
  feature: ReferenceProfileFeature,
): ReferenceNote {
  if (profile.profile_status !== ProfileStatus.READY) {
    return {
      severity: 'warn',
      title: 'This profile is not a complete training baseline.',
      detail: `Profile status is "${profile.profile_status}", so drift scores computed against it may be unreliable.`,
    }
  }
  return {
    severity: 'info',
    title: profile.baseline_label
      ? `This profile is the training baseline · ${profile.baseline_label}`
      : 'This profile is the training baseline.',
    detail: getReferenceNoteDetail(feature),
  }
}
