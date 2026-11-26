export function scaledDecimal(unscaled: string, scale: number): string {
  const sign = unscaled.startsWith('-') ? '-' : ''
  const digits = unscaled.slice(sign.length)
  if (scale <= 0) return sign + digits + '0'.repeat(-scale)
  const padded = digits.padStart(scale + 1, '0')
  return sign + padded.slice(0, -scale) + '.' + padded.slice(-scale)
}
