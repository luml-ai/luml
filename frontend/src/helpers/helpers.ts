import type { Validator } from '@/lib/api/satellites/interfaces'
import {
  Tasks,
  type ClassificationMetrics,
  type RegressionMetrics,
  type TrainingData,
} from '@/lib/data-processing/interfaces'
import { FNNX_PRODUCER_TAGS_MANIFEST_ENUM, FnnxService } from '@/lib/fnnx/FnnxService'
import type { ProviderSetting } from '@/lib/promt-fusion/prompt-fusion.interfaces'
import { z } from 'zod'

export const getMetrics = (
  data: Pick<
    TrainingData<ClassificationMetrics | RegressionMetrics>,
    'test_metrics' | 'train_metrics'
  >,
  task: Tasks,
  metricsType: 'test_metrics' | 'train_metrics',
) => {
  if (task === Tasks.TABULAR_CLASSIFICATION) {
    const metrics = data?.[metricsType] as ClassificationMetrics
    return FnnxService.getClassificationMetricsV1(metrics)
  } else {
    const metrics = data?.[metricsType] as RegressionMetrics
    return FnnxService.getRegressionMetricsV1(metrics)
  }
}

export const getFormattedMetric = (num: number | null | undefined) => {
  if (!num) return '0'
  if (Math.log10(Math.abs(num)) > 5) return formatNumberScientific(num)
  else if (Math.log10(Math.abs(num)) > 2) return num.toFixed()
  return num.toFixed(2)
}

export const getMetricsCards = (
  testValues: string[],
  trainingValues: string[],
  tag: FNNX_PRODUCER_TAGS_MANIFEST_ENUM,
) => {
  let titles: string[] = []
  if (tag === FNNX_PRODUCER_TAGS_MANIFEST_ENUM.tabular_classification_v1) {
    titles = ['Balanced accuracy', 'Precision', 'Recall', 'F1 score']
  } else {
    titles = ['Mean Squared Error', 'Root Mean Squared Error', 'Mean Absolute Error', 'R² Score']
  }
  return titles.map((title, index) => ({
    title,
    items: [{ value: testValues[index] }, { value: trainingValues[index] }],
  }))
}

export const toPercent = (float: number) => Number((float * 100).toFixed())

export const fixNumber = (float: number | null | undefined, decimals: number) =>
  float ? float.toFixed(decimals) : '0'

export const convertObjectToCsvBlob = (data: object) => {
  const headers = Object.keys(data)
  const rows = []
  const maxLength = Math.max(...headers.map((key) => (data[key as keyof typeof data] as []).length))
  for (let i = 0; i < maxLength; i++) {
    const row = headers.map((header) => data[header as keyof typeof data][i] ?? '')
    rows.push(row)
  }
  const csvContent = [
    headers.join(','),
    ...rows.map((row) => {
      return row.map((item) => (typeof item === 'object' ? JSON.stringify(item) : item))
    }),
  ].join('\n')
  return new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
}

export const formatNumberScientific = (num: number, significantDigits = 3) => {
  return new Intl.NumberFormat('en', {
    notation: 'scientific',
    maximumSignificantDigits: significantDigits,
  }).format(num)
}

export const cutStringOnMiddle = (string: string, length = 20) => {
  if (string.length < length) return string
  const startSubstring = string.slice(0, Math.floor(length / 2))
  const endSubstring = string.slice(Math.floor(-length / 2))
  return `${startSubstring}...${endSubstring}`
}

export const parseProviderSettingsToObject = (settings: ProviderSetting[] | null) => {
  if (!settings) return {}
  return (
    settings.reduce((acc: Record<string, string>, setting) => {
      acc[setting.id] = setting.value
      return acc
    }, {}) || {}
  )
}

export const getSha256 = async (buffer: ArrayBuffer): Promise<string> => {
  const hashBuffer = await crypto.subtle.digest('SHA-256', buffer)
  return [...new Uint8Array(hashBuffer)].map((b) => b.toString(16).padStart(2, '0')).join('')
}

export const getSizeText = (size: number) => {
  const value = size < 1000 ? size : size < 1000000 ? size / 1000 : size / 1000000
  const symbol = size < 1000 ? 'B' : size < 1000000 ? 'KB' : 'MB'
  return value.toFixed(2) + ' ' + symbol
}

export const downloadFileFromBlob = (blob: Blob, fileName: string) => {
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = fileName
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(link.href)
}

export const getLastUpdateText = (date: string | number | Date) => {
  const now = new Date()
  const updated = new Date(date)
  const diffMs = now.getTime() - updated.getTime()

  const diffSec = Math.floor(diffMs / 1000)
  const diffMin = Math.floor(diffSec / 60)
  const diffHr = Math.floor(diffMin / 60)
  const diffDay = Math.floor(diffHr / 24)
  const diffWeek = Math.floor(diffDay / 7)
  const diffMonth = Math.floor(diffDay / 30)
  const diffYear = Math.floor(diffDay / 365)

  if (diffHr < 1) {
    const mins = Math.max(1, diffMin)
    return `Last updated ${mins} minute${mins === 1 ? '' : 's'} ago`
  }

  if (diffDay < 1) {
    return `Last updated ${diffHr} hour${diffHr === 1 ? '' : 's'} ago`
  }

  if (diffDay < 7) {
    return `Last updated ${diffDay} day${diffDay === 1 ? '' : 's'} ago`
  }

  if (diffDay < 30) {
    return `Last updated ${diffWeek} week${diffWeek === 1 ? '' : 's'} ago`
  }

  if (diffDay < 365) {
    return `Last updated ${diffMonth} month${diffMonth === 1 ? '' : 's'} ago`
  }

  return `Last updated ${diffYear} year${diffYear === 1 ? '' : 's'} ago`
}

export const getErrorMessage = (error: any, message = 'Something went wrong') => {
  return error?.response?.detail?.message || error?.message || message
}

export const getNumberOrString = (string: string | number) => {
  const isNumber = !isNaN(+string)
  return isNumber ? +string : string
}

export function isYamlLike(text: string) {
  const trimmed = text.trim()
  if (!trimmed) return false
  if (tryParseJson(text) !== null) return true
  const hasKeyColon = /^[ \t-]*[A-Za-z_][A-Za-z0-9_-]*:\s+\S+/m.test(trimmed)
  const hasMultilineHyphen = /^\s*-\s+/m.test(trimmed)
  const hasYamlStart = /^---\s*$/m.test(trimmed)
  return hasKeyColon || hasMultilineHyphen || hasYamlStart
}

export function jsonToYaml(obj: any, indent = 0): string {
  const spaces = '  '.repeat(indent)
  if (Array.isArray(obj)) {
    return obj.map((v) => `${spaces}- ${jsonToYaml(v, indent + 1).trimStart()}`).join('\n')
  } else if (obj && typeof obj === 'object') {
    return Object.entries(obj)
      .map(([k, v]) => {
        if (Array.isArray(v)) {
          const arrayYaml = jsonToYaml(v, indent + 1)
          return `${spaces}${k}:\n${arrayYaml}`
        } else if (v && typeof v === 'object') {
          const nested = jsonToYaml(v, indent + 1)
          return `${spaces}${k}:\n${nested}`
        } else {
          return `${spaces}${k}: ${v}`
        }
      })
      .join('\n')
  }
  return String(obj)
}

function tryParseJson(text: string) {
  try {
    const trimmed = text.trim()
    if (!trimmed) return null
    return JSON.parse(trimmed)
  } catch (e) {
    return null
  }
}

export function getSatelliteValidator(config: Validator) {
  switch (config.type) {
    case 'min':
      return z.number().min(config.value)

    case 'max':
      return z.number().max(config.value)

    case 'regex':
      return z.string().regex(config.value)

    case 'equal':
      return z.any().refine((val) => val === config.value)

    case 'notEqual':
      return z.any().refine((val) => val !== config.value)

    case 'in':
      return z.any().refine((val) => config.value.includes(val))
  }
}

export function combineValidators(validators: z.ZodTypeAny[], required: boolean) {
  let schema: z.ZodTypeAny = z.any()

  for (const v of validators) {
    schema = schema.pipe(v)
  }

  if (!required) {
    schema = schema.optional()
  }

  return schema
}
