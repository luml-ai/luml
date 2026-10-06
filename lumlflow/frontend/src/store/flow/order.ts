interface DecimalParts {
  negative: boolean
  whole: string
  fraction: string
}

function decimalParts(value: string): DecimalParts {
  const negative = value.startsWith('-')
  const unsigned = value.replace(/^[+-]/, '')
  const [wholePart = '0', fractionPart = ''] = unsigned.split('.', 2)
  const whole = wholePart.replace(/^0+/, '') || '0'
  const fraction = fractionPart.replace(/0+$/, '')
  return {
    negative: negative && (whole !== '0' || fraction !== ''),
    whole,
    fraction,
  }
}

function compareMagnitude(left: DecimalParts, right: DecimalParts): number {
  if (left.whole.length !== right.whole.length) return left.whole.length - right.whole.length
  const whole = left.whole.localeCompare(right.whole)
  if (whole !== 0) return whole
  const width = Math.max(left.fraction.length, right.fraction.length)
  return left.fraction.padEnd(width, '0').localeCompare(right.fraction.padEnd(width, '0'))
}

export function compareOrder(left: string, right: string): number {
  const a = decimalParts(left)
  const b = decimalParts(right)
  if (a.negative !== b.negative) return a.negative ? -1 : 1
  const magnitude = compareMagnitude(a, b)
  return a.negative ? -magnitude : magnitude
}
