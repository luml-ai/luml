// Keep fractional ticks as integers, including for times before the Unix epoch.
export function formatTimestamp(ticks: bigint, digits: number): string {
  const scale = 10n ** BigInt(digits)
  const fraction = ((ticks % scale) + scale) % scale
  const seconds = (ticks - fraction) / scale
  const iso = new Date(Number(seconds) * 1000).toISOString()
  return digits ? iso.slice(0, -5) + '.' + String(fraction).padStart(digits, '0') + 'Z' : iso
}
