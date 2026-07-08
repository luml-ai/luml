import { Bot, Circle, MessageSquareMore, Ruler, Shuffle, Wrench } from 'lucide-vue-next'
import { MODELS_COLORS } from '../constants/colors'
import { SpanTypeEnum } from '../interfaces/interfaces'

export const getModelColorByIndex = (index: number) => {
  const color = MODELS_COLORS[index]
  if (color) {
    return color
  } else {
    return getRandomHexColor()
  }
}

export const safeParse = (text: any) => {
  if (typeof text !== 'string') return text
  try {
    return JSON.parse(text)
  } catch {
    return text
  }
}

export const cutStringOnMiddle = (string: string, length = 20) => {
  if (string.length < length) return string
  const startSubstring = string.slice(0, Math.floor(length / 2))
  const endSubstring = string.slice(Math.floor(-length / 2))
  return `${startSubstring}...${endSubstring}`
}

const getRandomHexColor = () => {
  return (
    '#' +
    Math.floor(Math.random() * 16777215)
      .toString(16)
      .padStart(6, '0')
  )
}

export const getSpanTypeData = (type: SpanTypeEnum | null) => {
  switch (type) {
    case SpanTypeEnum.AGENT:
      return { icon: Bot, color: 'var(--p-trace-span-icon-color-6)' }
    case SpanTypeEnum.CHAT:
      return { icon: MessageSquareMore, color: 'var(--p-trace-span-icon-color-2)' }
    case SpanTypeEnum.TOOL:
      return { icon: Wrench, color: 'var(--p-trace-span-icon-color-3)' }
    case SpanTypeEnum.EMBEDDER:
      return { icon: Ruler, color: 'var(--p-trace-span-icon-color-4)' }
    case SpanTypeEnum.RERANKER:
      return { icon: Shuffle, color: 'var(--p-trace-span-icon-color-5)' }
    default:
      return { icon: Circle, color: 'var(--p-trace-span-icon-color-1)' }
  }
}

export const getFormattedTime = (startNs: number, endNs: number) => {
  const ns = endNs - startNs
  return getFormattedExecutionTime(ns)
}

export const getFormattedExecutionTime = (ns: number) => {
  // Sub-microsecond magnitudes are precision noise from epoch-ns subtraction and
  // can even be negative after float64 rounding; never present them as exact.
  if (ns < 1_000) return '<1µs'

  // Round to each tier's displayed precision, then let a value sitting just under
  // a tier edge (e.g. 999,999ns) promote into the next tier instead of rendering
  // an artifact like "1000µs", "1000ms", or "60.00s".
  const micros = Math.round(ns / 1_000)
  if (micros < 1_000) return `${micros}µs`

  const millis = Math.round(ns / 1_000_000)
  if (millis < 1_000) return `${millis}ms`

  const secondsStr = (ns / 1_000_000_000).toFixed(2)
  if (Number(secondsStr) < 60) return `${secondsStr}s`

  const totalSeconds = Math.round(ns / 1_000_000_000)
  const minutes = Math.floor(totalSeconds / 60)
  if (minutes < 60) return `${minutes}min ${totalSeconds % 60}s`

  const totalMinutes = Math.round(ns / 60_000_000_000)
  const hours = Math.floor(totalMinutes / 60)
  if (hours < 24) return `${hours}h ${totalMinutes % 60}min`

  const totalHours = Math.round(ns / 3_600_000_000_000)
  const days = Math.floor(totalHours / 24)
  return `${days}d ${totalHours % 24}h`
}

export const getErrorMessage = (error: any, message = 'Something went wrong') => {
  return (
    error?.response?.data?.detail || error?.response?.detail?.message || error?.message || message
  )
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

export const formattedDate = (date: string | number | Date) => {
  return new Date(date).toLocaleString('en-US', {
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: 'numeric',
    minute: 'numeric',
    second: 'numeric',
    hour12: false,
  })
}
