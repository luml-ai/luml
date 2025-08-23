import { MODELS_COLORS } from '../constants/colors'

export const getModelColorByIndex = (index: number) => {
  return MODELS_COLORS[index] || MODELS_COLORS[MODELS_COLORS.length - 1]
}

export const safeParse = (text: any) => {
  if (typeof text !== 'string') return null
  return JSON.parse(text)
}

export const cutStringOnMiddle = (string: string, length = 20) => {
  if (string.length < length) return string
  const startSubstring = string.slice(0, Math.floor(length / 2))
  const endSubstring = string.slice(Math.floor(-length / 2))
  return `${startSubstring}...${endSubstring}`
}
