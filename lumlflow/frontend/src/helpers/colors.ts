import { ARTIFACTS_COLORS } from '@/constants/colors'

export const getArtifactColorByIndex = (index: number) => {
  const color = ARTIFACTS_COLORS[index]
  if (color) {
    return color
  } else {
    return getRandomHexColor()
  }
}

const getRandomHexColor = () => {
  return (
    '#' +
    Math.floor(Math.random() * 16777215)
      .toString(16)
      .padStart(6, '0')
  )
}
