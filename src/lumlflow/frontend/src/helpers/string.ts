export const cutStringOnMiddle = (string: string, length: number) => {
  if (string.length < length) return string
  const startSubstring = string.slice(0, Math.floor(length / 2))
  const endSubstring = string.slice(Math.floor(-length / 2))
  return `${startSubstring}...${endSubstring}`
}

export const getSizeText = (size: number) => {
  if (size < 1000) return `${size}B`
  if (size < 1000000) return `${size / 1000}KB`
  if (size < 1000000000) return `${size / 1000000}MB`
  return `${size / 1000000000}GB`
}
