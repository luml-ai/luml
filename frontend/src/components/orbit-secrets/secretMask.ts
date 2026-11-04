export const SECRET_MASK = '*'.repeat(15)

export function maskSecret(value?: string): string {
  if (!value) return SECRET_MASK
  return value.length > SECRET_MASK.length ? SECRET_MASK : '*'.repeat(value.length)
}
