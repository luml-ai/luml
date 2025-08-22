import { MODELS_COLORS } from '../constants/colors'

export const getModelColorByIndex = (index: number) => {
  return MODELS_COLORS[index] || MODELS_COLORS[MODELS_COLORS.length - 1]
}

export const safeParse = (text: any) => {
  if (typeof text !== 'string') return null
  return JSON.parse(text)
}
