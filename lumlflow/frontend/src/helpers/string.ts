export const cutStringOnMiddle = (string: string, length: number) => {
  if (string.length < length) return string
  const startSubstring = string.slice(0, Math.floor(length / 2))
  const endSubstring = string.slice(Math.floor(-length / 2))
  return `${startSubstring}...${endSubstring}`
}

export const capitalize = (string: string) => {
  if (!string) return string
  return string[0].toUpperCase() + string.slice(1)
}

export const getSizeText = (size: number, space = '') => {
  if (size < 1000) return `${size}${space}B`
  if (size < 1000000) return `${size / 1000}${space}KB`
  if (size < 1000000000) return `${size / 1000000}${space}MB`
  return `${size / 1000000000}${space}GB`
}
