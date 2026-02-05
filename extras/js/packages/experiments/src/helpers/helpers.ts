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

  if (ns < 1_000) {
    return `${ns}ns`
  }

  const ms = ns / 1_000_000
  if (ms < 1000) {
    return `${ms.toFixed(2)}ms`
  }

  const seconds = ms / 1000
  if (seconds < 60) {
    return `${seconds.toFixed(2)}s`
  }

  const minutes = seconds / 60
  if (minutes < 60) {
    return `${minutes.toFixed(2)}m`
  }

  const hours = minutes / 60
  if (hours < 24) {
    return `${hours.toFixed(2)}h`
  }

  const days = hours / 24
  return `${days.toFixed(2)}d`
}
